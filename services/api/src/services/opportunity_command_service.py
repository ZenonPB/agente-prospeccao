"""Comandos da Opportunity 360 sobre as fontes canônicas existentes.

Não cria uma segunda entidade de oportunidade comercial: a oferta continua em
``LeadOpportunityRow`` e o estado de trabalho continua em ``Lead`` /
``CommercialTask``. O serviço centraliza autorização, validação, auditoria e
idempotência para a UI 360.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from database.engagement_models import CommercialTask
from src.db.models import (
    Lead,
    LeadActivityAction,
    LeadOpportunityRow,
    LeadStatus,
    LostReason,
    NegotiationStage,
    OrganizationMember,
    OrganizationRole,
    SalesRole,
    User,
)
from src.services.lead_activity_service import log_activity, log_status_change, semantic_action_for
from src.services.org_service import consultant_lead_scope


class OpportunityNotFound(LookupError):
    pass


class OpportunityForbidden(PermissionError):
    pass


class OpportunityValidation(ValueError):
    pass


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OpportunityValidation(f"Data/hora inválida: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _enum(enum_cls, value: str | None, field: str):
    if value is None:
        return None
    try:
        return enum_cls(value)
    except ValueError as exc:
        raise OpportunityValidation(f"{field} inválido: {value}") from exc


def _can_write(member: OrganizationMember) -> bool:
    if member.role in (OrganizationRole.OWNER, OrganizationRole.ADMIN):
        return True
    return member.sales_role in (SalesRole.CONSULTOR, SalesRole.MANAGER)


def _can_manage_owners(member: OrganizationMember) -> bool:
    return (
        member.role in (OrganizationRole.OWNER, OrganizationRole.ADMIN)
        or member.sales_role == SalesRole.MANAGER
    )


class OpportunityCommandService:
    def __init__(self, db, organization_id: Any, member: OrganizationMember, user: User):
        self.db = db
        self.organization_id = organization_id
        self.member = member
        self.user = user
        # IDs primitivos sobrevivem a rollback/expire da Session e evitam lazy
        # load acidental no meio de uma operação de escrita/auditoria.
        self.user_id = user.id

    def _load(self, opportunity_id: Any) -> tuple[LeadOpportunityRow, Lead]:
        opportunity = self.db.query(LeadOpportunityRow).filter(
            LeadOpportunityRow.id == opportunity_id,
            LeadOpportunityRow.organization_id == self.organization_id,
        ).first()
        if opportunity is None:
            raise OpportunityNotFound("Oportunidade não encontrada")

        query = self.db.query(Lead).filter(
            Lead.id == opportunity.lead_id,
            Lead.organization_id == self.organization_id,
        )
        query = consultant_lead_scope(self.member, query)
        lead = query.first()
        if lead is None:
            # Fail-closed: não revela se a oportunidade existe fora da carteira.
            raise OpportunityNotFound("Oportunidade não encontrada")
        return opportunity, lead

    def _assert_write(self) -> None:
        if not _can_write(self.member):
            raise OpportunityForbidden("Seu papel permite leitura, mas não edição comercial")

    def update(self, opportunity_id: Any, data: dict[str, Any]) -> dict[str, Any]:
        self._assert_write()
        opportunity, lead = self._load(opportunity_id)
        changed: dict[str, Any] = {}

        if "owner_user_id" in data:
            self._set_owner(lead, data.get("owner_user_id"), changed)

        # Valida o estado final antes de alterar o ORM. Status e motivo de perda
        # formam uma única invariável no banco; tratar os dois atomicamente evita
        # autoflush intermediário que viole ck_leads_lost_reason_required.
        requested_status = (
            _enum(LeadStatus, data.get("status"), "status")
            if "status" in data
            else lead.status
        )
        requested_lost_reason = (
            _enum(LostReason, data.get("lost_reason"), "lost_reason")
            if "lost_reason" in data
            else lead.lost_reason
        )
        if requested_status == LeadStatus.PERDIDO and requested_lost_reason is None:
            raise OpportunityValidation("Informe o motivo da perda")

        # Atribui o motivo antes do status para que qualquer query de auditoria
        # posterior faça flush de um estado que já satisfaz a constraint.
        if "lost_reason" in data and lead.lost_reason != requested_lost_reason:
            lead.lost_reason = requested_lost_reason
            changed["lost_reason"] = requested_lost_reason.value if requested_lost_reason else None

        if "status" in data:
            new_status = requested_status
            if new_status is not None and new_status != lead.status:
                previous = lead.status
                lead.status = new_status
                log_status_change(
                    self.db,
                    lead,
                    user_id=str(self.user_id),
                    status_to=new_status,
                    status_from=previous,
                    detail=f"{previous.value if previous else '?'} → {new_status.value}",
                )
                semantic = semantic_action_for(new_status)
                if semantic:
                    log_activity(
                        self.db,
                        lead,
                        action=semantic,
                        user_id=str(self.user_id),
                        status_to=new_status,
                        detail=new_status.value,
                    )
                changed["status"] = new_status.value

        if "negotiation_stage" in data:
            value = _enum(NegotiationStage, data.get("negotiation_stage"), "negotiation_stage")
            if lead.negotiation_stage != value:
                lead.negotiation_stage = value
                changed["negotiation_stage"] = value.value if value else None

        if "value" in data:
            raw = data.get("value")
            value = None if raw is None else float(raw)
            if value is not None and value < 0:
                raise OpportunityValidation("value não pode ser negativo")
            if lead.value != value:
                lead.value = value
                changed["value"] = value

        if "expected_close_date" in data:
            value = _parse_datetime(data.get("expected_close_date"))
            if lead.expected_close_date != value:
                lead.expected_close_date = value
                changed["expected_close_date"] = value.isoformat() if value else None

        if "next_action_at" in data:
            value = _parse_datetime(data.get("next_action_at"))
            if lead.next_action_at != value:
                lead.next_action_at = value
                changed["next_action_at"] = value.isoformat() if value else None

        if "notes" in data:
            value = data.get("notes")
            value = value.strip() if isinstance(value, str) else None
            if value == "":
                value = None
            if lead.notes != value:
                lead.notes = value
                changed["notes"] = value

        if not changed:
            return self._result(opportunity, lead, changed)

        # Uma única atividade resume alterações de campos não cobertas por uma
        # activity semântica própria. Não duplica status/assign quando já logados.
        non_semantic = {
            key: value for key, value in changed.items()
            if key not in {"status", "owner_user_id"}
        }
        if non_semantic:
            log_activity(
                self.db,
                lead,
                action=LeadActivityAction.NEGOTIATION_UPDATED,
                user_id=str(self.user_id),
                detail="Opportunity 360: " + ", ".join(sorted(non_semantic)),
            )

        self.db.commit()
        self.db.refresh(lead)
        return self._result(opportunity, lead, changed)

    def _set_owner(self, lead: Lead, owner_user_id: str | None, changed: dict[str, Any]) -> None:
        current = str(lead.assigned_to_id) if lead.assigned_to_id else None
        target = str(owner_user_id) if owner_user_id else None
        if current == target:
            return

        if not _can_manage_owners(self.member):
            # CONSULTOR pode assumir lead livre/próprio e pode liberar o próprio,
            # mas nunca atribuir um colega ou tomar carteira alheia.
            if target not in {None, str(self.member.user_id)}:
                raise OpportunityForbidden("Consultor só pode atribuir a oportunidade a si mesmo")
            if current not in {None, str(self.member.user_id)}:
                raise OpportunityForbidden("Oportunidade pertence a outro consultor")

        owner = None
        if target is not None:
            owner = self.db.query(User).filter(User.id == target).first()
            target_member = self.db.query(OrganizationMember).filter(
                OrganizationMember.organization_id == self.organization_id,
                OrganizationMember.user_id == target,
            ).first()
            if owner is None or target_member is None:
                raise OpportunityValidation("Responsável não pertence ao workspace")

        lead.assigned_to_id = owner.id if owner else None
        lead.assigned_at = datetime.now(timezone.utc) if owner else None
        log_activity(
            self.db,
            lead,
            action=LeadActivityAction.ASSIGNED if owner else LeadActivityAction.UNASSIGNED,
            user_id=str(self.user_id),
            detail=f"Atribuído a {owner.name}" if owner else "Oportunidade desatribuída",
        )
        changed["owner_user_id"] = str(owner.id) if owner else None

    def create_task(self, opportunity_id: Any, data: dict[str, Any]) -> dict[str, Any]:
        self._assert_write()
        _opportunity, lead = self._load(opportunity_id)
        client_request_id = str(data.get("client_request_id") or "").strip()
        if len(client_request_id) < 8:
            raise OpportunityValidation("client_request_id deve ter ao menos 8 caracteres")
        idempotency_key = f"opportunity360:{opportunity_id}:{client_request_id}"[:160]

        existing = self.db.query(CommercialTask).filter(
            CommercialTask.organization_id == self.organization_id,
            CommercialTask.idempotency_key == idempotency_key,
        ).first()
        if existing is not None:
            return self._task(existing, created=False)

        owner_user_id = data.get("owner_user_id") or lead.assigned_to_id or self.member.user_id
        target_member = self.db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == self.organization_id,
            OrganizationMember.user_id == owner_user_id,
        ).first()
        if target_member is None:
            raise OpportunityValidation("Responsável da tarefa não pertence ao workspace")
        if not _can_manage_owners(self.member) and str(owner_user_id) != str(self.member.user_id):
            raise OpportunityForbidden("Consultor só pode criar tarefa para si mesmo")

        title = str(data.get("title") or "").strip()
        if not title:
            raise OpportunityValidation("Título da tarefa é obrigatório")
        due_at = _parse_datetime(data.get("due_at"))
        task = CommercialTask(
            organization_id=self.organization_id,
            lead_id=lead.id,
            person_id=lead.primary_person_id,
            owner_user_id=owner_user_id,
            task_type=str(data.get("task_type") or "FOLLOW_UP").strip().upper()[:32],
            title=title[:180],
            description=(str(data.get("description")).strip()[:4000] if data.get("description") else None),
            due_at=due_at,
            status="OPEN",
            source="opportunity360",
            source_ref=str(opportunity_id),
            idempotency_key=idempotency_key,
            task_metadata={"lead_opportunity_id": str(opportunity_id)},
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return self._task(task, created=True)

    def update_task(self, opportunity_id: Any, task_id: Any, data: dict[str, Any]) -> dict[str, Any]:
        self._assert_write()
        _opportunity, lead = self._load(opportunity_id)
        task = self.db.query(CommercialTask).filter(
            CommercialTask.id == task_id,
            CommercialTask.organization_id == self.organization_id,
            CommercialTask.lead_id == lead.id,
        ).first()
        if task is None:
            raise OpportunityNotFound("Tarefa não encontrada")

        if not _can_manage_owners(self.member) and str(task.owner_user_id) not in {"None", str(self.member.user_id)}:
            raise OpportunityForbidden("Tarefa pertence a outro consultor")

        if "title" in data:
            title = str(data.get("title") or "").strip()
            if not title:
                raise OpportunityValidation("Título da tarefa é obrigatório")
            task.title = title[:180]
        if "description" in data:
            task.description = str(data.get("description") or "").strip()[:4000] or None
        if "due_at" in data:
            task.due_at = _parse_datetime(data.get("due_at"))
        if "status" in data:
            status = str(data.get("status") or "").strip().upper()
            if status not in {"OPEN", "COMPLETED", "DISMISSED"}:
                raise OpportunityValidation("status da tarefa inválido")
            task.status = status
            task.completed_at = datetime.now(timezone.utc) if status == "COMPLETED" else None
        if "owner_user_id" in data:
            owner_user_id = data.get("owner_user_id")
            if owner_user_id is None:
                task.owner_user_id = None
            else:
                target_member = self.db.query(OrganizationMember).filter(
                    OrganizationMember.organization_id == self.organization_id,
                    OrganizationMember.user_id == owner_user_id,
                ).first()
                if target_member is None:
                    raise OpportunityValidation("Responsável da tarefa não pertence ao workspace")
                if not _can_manage_owners(self.member) and str(owner_user_id) != str(self.member.user_id):
                    raise OpportunityForbidden("Consultor só pode atribuir tarefa a si mesmo")
                task.owner_user_id = owner_user_id

        self.db.commit()
        self.db.refresh(task)
        return self._task(task, created=False)

    @staticmethod
    def _task(task: CommercialTask, *, created: bool) -> dict[str, Any]:
        return {
            "id": str(task.id),
            "created": created,
            "lead_id": str(task.lead_id),
            "owner_user_id": str(task.owner_user_id) if task.owner_user_id else None,
            "task_type": task.task_type,
            "title": task.title,
            "description": task.description,
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "status": task.status,
            "source": task.source,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }

    @staticmethod
    def _result(opportunity: LeadOpportunityRow, lead: Lead, changed: dict[str, Any]) -> dict[str, Any]:
        return {
            "opportunity_id": str(opportunity.id),
            "lead_id": str(lead.id),
            "changed": changed,
            "commercial": {
                "owner_user_id": str(lead.assigned_to_id) if lead.assigned_to_id else None,
                "status": lead.status.value if lead.status else None,
                "negotiation_stage": lead.negotiation_stage.value if lead.negotiation_stage else None,
                "value": float(lead.value) if lead.value is not None else None,
                "expected_close_date": lead.expected_close_date.isoformat() if lead.expected_close_date else None,
                "next_action_at": lead.next_action_at.isoformat() if lead.next_action_at else None,
                "lost_reason": lead.lost_reason.value if lead.lost_reason else None,
                "notes": lead.notes,
            },
        }
