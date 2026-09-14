"""Comandos bulk tenant-safe para operações comerciais em leads.

A tabela de operações é apenas uma âncora técnica de idempotência. O estado
comercial continua em ``Lead`` e a trilha continua em ``LeadActivity``.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
import uuid
import binascii
from typing import Any

logger = logging.getLogger(__name__)

from sqlalchemy.exc import IntegrityError

from src.db.models import (
    CommercialBulkOperation,
    Lead,
    LeadActivityAction,
    LeadStatus,
    LostReason,
    OrganizationMember,
    OrganizationRole,
    SalesRole,
    User,
)
from src.services.lead_activity_service import log_activity
from src.services.lead_status_service import transition_lead_status
from src.services.org_service import consultant_lead_scope, is_full_access

MAX_ITEMS = 100


class BulkCommandValidation(ValueError):
    """Payload bulk inválido antes de consultar ou mutar o domínio."""


class BulkCommandForbidden(PermissionError):
    """O membro autenticado não pode executar a operação."""


class BulkCommandConflict(RuntimeError):
    """A chave de idempotência já foi usada com outro payload."""


def _as_uuid(value: Any, field: str) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError, binascii.Error) as exc:
        raise BulkCommandValidation(f"{field} inválido") from exc


def _parse_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise BulkCommandValidation(f"{field} inválido")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise BulkCommandValidation(f"{field} inválido") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _enum_value(value: Any) -> str | None:
    return getattr(value, "value", value)


def normalize_bulk_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normaliza o corpo sem a chave de idempotência para fingerprint estável."""
    allowed_fields = {
        "operation", "lead_ids", "status", "lost_reason", "assigned_to_id",
        "expected_updated_at",
    }
    unknown = sorted(set(payload) - allowed_fields)
    if unknown:
        raise BulkCommandValidation(
            "Campo(s) não permitido(s): " + ", ".join(unknown)
        )

    operation = str(_enum_value(payload.get("operation") or "")).strip().lower()
    if operation not in {"status", "assign"}:
        raise BulkCommandValidation("operation deve ser status ou assign")

    raw_ids = payload.get("lead_ids")
    if not isinstance(raw_ids, list) or not 1 <= len(raw_ids) <= MAX_ITEMS:
        raise BulkCommandValidation(f"lead_ids deve conter entre 1 e {MAX_ITEMS} itens")
    lead_ids = [str(_as_uuid(item, "lead_id")) for item in raw_ids]
    if len(set(lead_ids)) != len(lead_ids):
        raise BulkCommandValidation("lead_ids não pode conter duplicatas")

    status = _enum_value(payload.get("status"))
    if operation == "status":
        if status is None:
            raise BulkCommandValidation("status é obrigatório para operation=status")
        try:
            status = LeadStatus(str(status)).value
        except ValueError as exc:
            raise BulkCommandValidation(f"status inválido: {status}") from exc
    else:
        status = None

    lost_reason = _enum_value(payload.get("lost_reason"))
    if status == LeadStatus.PERDIDO.value:
        if lost_reason is None:
            raise BulkCommandValidation("lost_reason é obrigatório para PERDIDO")
        try:
            lost_reason = LostReason(str(lost_reason)).value
        except ValueError as exc:
            raise BulkCommandValidation(f"lost_reason inválido: {lost_reason}") from exc
    else:
        lost_reason = None

    assigned_to_id = None
    if operation == "assign" and payload.get("assigned_to_id") is not None:
        assigned_to_id = str(_as_uuid(payload["assigned_to_id"], "assigned_to_id"))

    expected = payload.get("expected_updated_at") or {}
    if not isinstance(expected, dict):
        raise BulkCommandValidation("expected_updated_at deve ser um mapa")
    lead_id_set = set(lead_ids)
    normalized_expected: dict[str, str] = {}
    for lead_id, value in expected.items():
        normalized_id = str(_as_uuid(lead_id, "expected_updated_at"))
        if normalized_id not in lead_id_set:
            continue
        normalized_expected[normalized_id] = _parse_datetime(value, "expected_updated_at").astimezone(timezone.utc).isoformat()

    return {
        "operation": operation,
        "lead_ids": lead_ids,
        "status": status,
        "lost_reason": lost_reason,
        "assigned_to_id": assigned_to_id,
        "expected_updated_at": dict(sorted(normalized_expected.items())),
    }


def fingerprint_payload(payload: dict[str, Any]) -> str:
    """Calcula o hash do contrato normalizado, sem ``idempotency_key``."""
    canonical = normalize_bulk_payload(payload)
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _result_item(lead_id: str, status: str, reason: str | None = None) -> dict[str, str | None]:
    return {"id": lead_id, "status": status, "reason": reason}


class LeadBulkCommandService:
    def __init__(self, db, organization_id: Any, member: OrganizationMember, user: User):
        self.db = db
        self.organization_id = organization_id
        self.member = member
        self.user = user
        self.user_id = user.id

    def _assert_write(self) -> None:
        # ANALYST permanece explicitamente read-only mesmo quando possui papel
        # administrativo herdado no workspace.
        if self.member.sales_role == SalesRole.ANALYST:
            raise BulkCommandForbidden("ANALYST possui acesso somente de leitura")
        if self.member.role in (OrganizationRole.OWNER, OrganizationRole.ADMIN):
            return
        if self.member.sales_role in (SalesRole.CONSULTOR, SalesRole.MANAGER):
            return
        raise BulkCommandForbidden("Seu papel não pode executar operações bulk")

    def _target_member(self, payload: dict[str, Any]):
        if payload["operation"] != "assign" or payload["assigned_to_id"] is None:
            return None
        target_id = _as_uuid(payload["assigned_to_id"], "assigned_to_id")
        target = self.db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == self.organization_id,
            OrganizationMember.user_id == target_id,
        ).first()
        if target is None:
            raise BulkCommandValidation("Responsável não pertence ao workspace")
        if not is_full_access(self.member) and target_id != self.member.user_id:
            raise BulkCommandForbidden("Consultor só pode autoatribuir leads")
        return target

    def _plan(self, payload: dict[str, Any], *, lock: bool = False) -> dict[str, Any]:
        normalized = normalize_bulk_payload(payload)
        target_member = self._target_member(normalized)
        ids = [uuid.UUID(value) for value in normalized["lead_ids"]]
        query = self.db.query(Lead).filter(
            Lead.organization_id == self.organization_id,
            Lead.id.in_(ids),
        )
        query = consultant_lead_scope(self.member, query)
        if lock and hasattr(query, "with_for_update"):
            query = query.with_for_update()
        leads = query.all()
        by_id = {str(lead.id): lead for lead in leads}
        accepted_ids: list[str] = []
        rejected: list[dict[str, str]] = []
        current_versions: dict[str, str | None] = {}
        expected = normalized["expected_updated_at"]

        for lead_id in normalized["lead_ids"]:
            lead = by_id.get(lead_id)
            if lead is None:
                rejected.append({"id": lead_id, "reason": "NOT_FOUND_OR_UNAUTHORIZED"})
                continue
            current_versions[lead_id] = _iso(lead.updated_at)
            if lead.updated_at is None:
                rejected.append({"id": lead_id, "reason": "VERSION_CONFLICT"})
                continue
            expected_value = expected.get(lead_id)
            if expected_value is not None:
                current_value = _parse_datetime(expected_value, "expected_updated_at")
                if lead.updated_at != current_value:
                    rejected.append({"id": lead_id, "reason": "VERSION_CONFLICT"})
                    continue
            if normalized["operation"] == "assign" and not is_full_access(self.member):
                if lead.assigned_to_id not in (None, self.member.user_id):
                    rejected.append({"id": lead_id, "reason": "NOT_AUTHORIZED"})
                    continue
            accepted_ids.append(lead_id)

        return {
            "operation": normalized["operation"],
            "total_selected": len(normalized["lead_ids"]),
            "accepted_ids": accepted_ids,
            "rejected": rejected,
            "current_versions": current_versions,
            "max_items": MAX_ITEMS,
            "_normalized": normalized,
            "_target_member": target_member,
            "_leads": by_id,
        }

    @staticmethod
    def _public_plan(plan: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in plan.items() if not key.startswith("_")}

    def preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._public_plan(self._plan(payload))

    def _apply_status(self, lead: Lead, payload: dict[str, Any]) -> tuple[bool, str | None]:
        new_status = LeadStatus(payload["status"])
        new_reason = LostReason(payload["lost_reason"]) if payload["lost_reason"] else None
        previous_status = lead.status
        previous_reason = lead.lost_reason
        if previous_status == new_status and previous_reason == new_reason:
            return False, "ALREADY_IN_DESIRED_STATE"

        activity = transition_lead_status(
            self.db,
            lead,
            new_status,
            user_id=str(self.user_id),
            lost_reason=new_reason,
        )
        outcome_by_status = {
            LeadStatus.RESPONDIDO: "RESPONDED",
            LeadStatus.REUNIAO_MARCADA: "MEETING",
            LeadStatus.REUNIAO_FEITA: "MEETING",
            LeadStatus.PERDIDO: "LOST",
        }
        outcome = outcome_by_status.get(new_status)
        if outcome:
            try:
                from services.prospecting.commercial_outcome_service import CommercialOutcomeService

                CommercialOutcomeService().record_for_lead(
                    self.db,
                    lead.organization_id,
                    lead.id,
                    outcome=outcome,
                    event_key=f"activity:{getattr(activity, 'id', None)}",
                )
            except Exception as exc:  # noqa: BLE001
                # O status/trilha são a fonte operacional; outcome alimenta
                # learning e não deve desfazer a transição comercial.
                logger.warning("Falha ao persistir outcome bulk do lead %s: %s", lead.id, exc)
        return True, None

    def _apply_assign(self, lead: Lead, payload: dict[str, Any]) -> tuple[bool, str | None]:
        target_id = _as_uuid(payload["assigned_to_id"], "assigned_to_id") if payload["assigned_to_id"] else None
        if lead.assigned_to_id == target_id:
            return False, "ALREADY_IN_DESIRED_STATE"
        lead.assigned_to_id = target_id
        lead.assigned_at = datetime.now(timezone.utc) if target_id else None
        action = LeadActivityAction.ASSIGNED if target_id else LeadActivityAction.UNASSIGNED
        log_activity(
            self.db,
            lead,
            action=action,
            user_id=str(self.user_id),
            detail=f"Bulk: atribuído a {target_id}" if target_id else "Bulk: lead desatribuído",
        )
        return True, None

    def execute(self, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        self._assert_write()
        if not isinstance(idempotency_key, str) or not 8 <= len(idempotency_key) <= 160:
            raise BulkCommandValidation("idempotency_key deve ter entre 8 e 160 caracteres")
        normalized = normalize_bulk_payload(payload)
        payload_hash = fingerprint_payload(normalized)
        existing = self.db.query(CommercialBulkOperation).filter(
            CommercialBulkOperation.organization_id == self.organization_id,
            CommercialBulkOperation.idempotency_key == idempotency_key,
        ).first()
        if existing is not None:
            if existing.payload_hash != payload_hash:
                raise BulkCommandConflict("idempotency_key já foi usada com outro payload")
            replay = dict(existing.result or {})
            replay["replayed"] = True
            return replay

        operation = CommercialBulkOperation(
            organization_id=self.organization_id,
            actor_id=self.user_id,
            idempotency_key=idempotency_key,
            operation=normalized["operation"],
            payload_hash=payload_hash,
            status="RUNNING",
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(operation)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            existing = self.db.query(CommercialBulkOperation).filter(
                CommercialBulkOperation.organization_id == self.organization_id,
                CommercialBulkOperation.idempotency_key == idempotency_key,
            ).first()
            if existing is not None and existing.payload_hash == payload_hash:
                replay = dict(existing.result or {})
                replay["replayed"] = True
                return replay
            if existing is not None:
                raise BulkCommandConflict("idempotency_key já foi usada com outro payload")
            raise

        plan = self._plan(normalized, lock=True)
        item_results = {
            item["id"]: _result_item(item["id"], "REJECTED", item["reason"])
            for item in plan["rejected"]
        }
        accepted = duplicate = failed = 0
        lead_ids = set(plan["accepted_ids"])
        by_id = plan["_leads"]
        for lead_id in normalized["lead_ids"]:
            if lead_id not in lead_ids:
                continue
            lead = by_id.get(lead_id)
            if lead is None:
                item_results[lead_id] = _result_item(
                    lead_id, "REJECTED", "NOT_FOUND_OR_UNAUTHORIZED"
                )
                continue
            try:
                with self.db.begin_nested():
                    changed, reason = (
                        self._apply_status(lead, normalized)
                        if normalized["operation"] == "status"
                        else self._apply_assign(lead, normalized)
                    )
                    self.db.flush()
                if changed:
                    accepted += 1
                    item_results[lead_id] = _result_item(lead_id, "ACCEPTED")
                else:
                    duplicate += 1
                    item_results[lead_id] = _result_item(lead_id, "DUPLICATE", reason)
            except Exception:
                failed += 1
                item_results[lead_id] = _result_item(
                    lead_id, "FAILED", "ITEM_MUTATION_FAILED"
                )

        items = [item_results[lead_id] for lead_id in normalized["lead_ids"]]
        rejected_count = sum(item["status"] == "REJECTED" for item in items)
        completed_at = datetime.now(timezone.utc)
        result = {
            "operation": normalized["operation"],
            "idempotency_key": idempotency_key,
            "replayed": False,
            "total_selected": len(normalized["lead_ids"]),
            "accepted": accepted,
            "duplicate": duplicate,
            "rejected": rejected_count,
            "failed": failed,
            "items": items,
            "created_at": _iso(operation.created_at),
            "completed_at": completed_at.isoformat(),
            "summary": {
                "accepted": accepted,
                "duplicate": duplicate,
                "rejected": rejected_count,
                "failed": failed,
            },
        }
        operation.status = "COMPLETED"
        operation.result = result
        operation.completed_at = completed_at
        self.db.commit()
        return result
