"""Central operacional do CRM: fila diária, busca global e visões salvas.

A camada agrega fontes canônicas; não persiste um segundo estado comercial.
Toda consulta começa pelo workspace e, para consultores, pela carteira visível.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import or_

from database.crm_models import CommercialSavedView
from database.engagement_models import CommercialTask, NextBestActionDecision
from src.db.models import Campaign, Company, Lead, LeadOpportunityRow, Person
from src.services.org_service import consultant_lead_scope, is_full_access


SAVED_VIEW_KINDS = {"crm", "analytics"}
SAVED_FILTER_KEYS = {
    "from", "to", "campaign_id", "consultant_id", "offer_key", "offer_version",
    "channel", "status", "score_bucket", "outcome", "attribution", "search",
    "segment", "city", "state", "negotiation_stage", "priority", "assigned",
    "min_score", "archived", "tag",
}
EPHEMERAL_FILTER_KEYS = {"cursor", "offset", "page", "limit"}
ARRAY_FILTER_KEYS = {"channel", "status", "score_bucket", "outcome", "negotiation_stage"}


class SalesOperatingValidation(ValueError):
    pass


class SalesOperatingForbidden(PermissionError):
    pass


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def normalize_saved_filters(filters: dict[str, Any]) -> dict[str, Any]:
    """Mantém somente filtros serializáveis e conhecidos, de modo determinístico.

    Paginação é deliberadamente descartada: uma visão salva representa critérios
    comerciais, não a página que estava aberta no momento do salvamento.
    """
    if not isinstance(filters, dict):
        raise SalesOperatingValidation("filters deve ser um objeto")
    unknown = sorted(set(filters) - SAVED_FILTER_KEYS - EPHEMERAL_FILTER_KEYS)
    if unknown:
        raise SalesOperatingValidation("Filtro(s) não suportado(s): " + ", ".join(unknown))
    normalized: dict[str, Any] = {}
    for key in sorted(filters):
        if key in EPHEMERAL_FILTER_KEYS:
            continue
        value = filters[key]
        if value is None or value == "":
            continue
        if key in ARRAY_FILTER_KEYS:
            if not isinstance(value, list):
                raise SalesOperatingValidation(f"{key} deve ser uma lista")
            clean = sorted({str(item).strip() for item in value if str(item).strip()})
            if clean:
                normalized[key] = clean
            continue
        text = str(value).strip()
        if not text:
            continue
        if key == "search" and len(text) > 200:
            raise SalesOperatingValidation("search deve ter no máximo 200 caracteres")
        normalized[key] = text
    return normalized


class SalesOperatingService:
    def __init__(self, db, organization_id: Any, member: Any, user: Any):
        self.db = db
        self.organization_id = organization_id
        self.member = member
        self.user = user

    def _visible_leads_query(self):
        query = self.db.query(Lead).filter(Lead.organization_id == self.organization_id)
        return consultant_lead_scope(self.member, query)

    def queue(self, limit: int = 20) -> dict[str, Any]:
        """Monta uma fila priorizada a partir de tarefas, recomendações e estado do lead."""
        limit = max(1, min(int(limit), 50))
        now = datetime.now(timezone.utc)
        leads = self._visible_leads_query().order_by(
            Lead.qualification_score.desc().nullslast(), Lead.updated_at.desc(), Lead.id.asc()
        ).limit(250).all()
        if not leads:
            return {"items": [], "total": 0, "as_of": now.isoformat()}

        lead_ids = [lead.id for lead in leads]
        tasks = self.db.query(CommercialTask).filter(
            CommercialTask.organization_id == self.organization_id,
            CommercialTask.lead_id.in_(lead_ids),
            CommercialTask.status.notin_(["COMPLETED", "CANCELLED"]),
        ).order_by(CommercialTask.due_at.asc().nullsfirst(), CommercialTask.id.asc()).all()
        decisions = self.db.query(NextBestActionDecision).filter(
            NextBestActionDecision.organization_id == self.organization_id,
            NextBestActionDecision.lead_id.in_(lead_ids),
            NextBestActionDecision.status == "PENDING",
        ).order_by(NextBestActionDecision.created_at.desc()).all()
        opportunities = self.db.query(LeadOpportunityRow).filter(
            LeadOpportunityRow.organization_id == self.organization_id,
            LeadOpportunityRow.lead_id.in_(lead_ids),
        ).order_by(LeadOpportunityRow.score.desc(), LeadOpportunityRow.id.asc()).all()

        task_by_lead: dict[str, CommercialTask] = {}
        for task in tasks:
            task_by_lead.setdefault(str(task.lead_id), task)
        decision_by_lead: dict[str, NextBestActionDecision] = {}
        for decision in decisions:
            decision_by_lead.setdefault(str(decision.lead_id), decision)
        opportunity_by_lead: dict[str, LeadOpportunityRow] = {}
        for opportunity in opportunities:
            opportunity_by_lead.setdefault(str(opportunity.lead_id), opportunity)

        items: list[dict[str, Any]] = []
        terminal = {"PERDIDO", "DESQUALIFICADO"}
        for lead in leads:
            status = getattr(lead.status, "value", lead.status)
            if status in terminal:
                continue
            key = str(lead.id)
            task = task_by_lead.get(key)
            decision = decision_by_lead.get(key)
            opportunity = opportunity_by_lead.get(key)
            reasons: list[str] = []
            priority = 20
            due_at = None

            if task is not None:
                due_at = task.due_at
                if task.due_at and task.due_at <= now:
                    reasons.append("Tarefa vencida")
                    priority = max(priority, 100)
                else:
                    reasons.append("Tarefa aberta")
                    priority = max(priority, 72)
            next_action_at = getattr(lead, "next_action_at", None)
            if next_action_at and next_action_at <= now:
                reasons.append("Próxima ação atrasada")
                priority = max(priority, 96)
                due_at = due_at or next_action_at
            if status == "PROPOSTA_ENVIADA":
                reasons.append("Proposta aguardando retorno")
                priority = max(priority, 88)
            if status == "QUALIFICADO" and getattr(lead, "last_contacted_at", None) is None:
                reasons.append("Aguardando primeiro contato")
                priority = max(priority, 82)
            lead_priority = getattr(getattr(lead, "priority", None), "value", getattr(lead, "priority", None))
            if lead_priority == "HOT":
                reasons.append("Oportunidade quente")
                priority = max(priority, 90)
            if opportunity is not None and int(opportunity.score or 0) >= 80:
                reasons.append("Alta aderência à oferta")
                priority = max(priority, 84)
            if decision is not None:
                reasons.append("Recomendação disponível")
                priority = max(priority, 76 + int(float(decision.confidence or 0) * 10))
                due_at = due_at or decision.deadline

            if not reasons:
                continue
            items.append({
                "lead_id": key,
                "company_name": lead.company_name,
                "status": status,
                "priority": priority,
                "qualification_score": lead.qualification_score,
                "offer_key": opportunity.offer_key if opportunity else (decision.offer_key if decision else None),
                "opportunity_score": opportunity.score if opportunity else None,
                "reasons": reasons,
                "recommended_action": decision.action if decision else (task.title if task else None),
                "recommended_why": decision.why if decision else None,
                "due_at": _iso(due_at),
                "owner_user_id": str(lead.assigned_to_id) if lead.assigned_to_id else None,
            })

        items.sort(key=lambda item: (-item["priority"], item["due_at"] or "9999", item["lead_id"]))
        return {"items": items[:limit], "total": len(items), "as_of": now.isoformat()}

    def search(self, query_text: str, limit: int = 8) -> dict[str, Any]:
        text = (query_text or "").strip()
        if len(text) < 2:
            raise SalesOperatingValidation("Digite pelo menos 2 caracteres")
        if len(text) > 120:
            raise SalesOperatingValidation("Busca deve ter no máximo 120 caracteres")
        limit = max(1, min(int(limit), 20))
        pattern = f"%{text}%"

        visible_leads = self._visible_leads_query().filter(
            or_(Lead.company_name.ilike(pattern), Lead.category.ilike(pattern), Lead.city.ilike(pattern))
        ).order_by(Lead.qualification_score.desc().nullslast(), Lead.id.asc()).limit(limit).all()

        all_visible = self._visible_leads_query().with_entities(Lead.id, Lead.company_id, Lead.primary_person_id).all()
        visible_lead_ids = {row[0] for row in all_visible}
        company_ids = {row[1] for row in all_visible if row[1] is not None}
        person_ids = {row[2] for row in all_visible if row[2] is not None}

        company_query = self.db.query(Company).filter(
            Company.organization_id == self.organization_id,
            or_(Company.company_name.ilike(pattern), Company.name.ilike(pattern), Company.cnpj.ilike(pattern)),
        )
        person_query = self.db.query(Person).filter(
            Person.organization_id == self.organization_id,
            or_(Person.name.ilike(pattern), Person.email.ilike(pattern), Person.role_label.ilike(pattern)),
        )
        if not is_full_access(self.member):
            if company_ids:
                company_query = company_query.filter(Company.id.in_(company_ids))
            else:
                company_query = company_query.filter(False)
            if company_ids or person_ids:
                person_query = person_query.filter(or_(Person.id.in_(person_ids), Person.company_id.in_(company_ids)))
            else:
                person_query = person_query.filter(False)

        companies = company_query.order_by(Company.company_name.asc(), Company.id.asc()).limit(limit).all()
        persons = person_query.order_by(Person.name.asc(), Person.id.asc()).limit(limit).all()
        opportunities = []
        if visible_lead_ids:
            opportunities = self.db.query(LeadOpportunityRow).filter(
                LeadOpportunityRow.organization_id == self.organization_id,
                LeadOpportunityRow.lead_id.in_(visible_lead_ids),
                LeadOpportunityRow.offer_key.ilike(pattern),
            ).order_by(LeadOpportunityRow.score.desc(), LeadOpportunityRow.id.asc()).limit(limit).all()

        campaigns = []
        if is_full_access(self.member):
            campaigns = self.db.query(Campaign).filter(
                Campaign.organization_id == self.organization_id,
                Campaign.name.ilike(pattern),
            ).order_by(Campaign.name.asc(), Campaign.id.asc()).limit(limit).all()

        return {
            "query": text,
            "groups": {
                "companies": [{"id": str(item.id), "title": item.company_name, "subtitle": item.city, "href": f"/crm/empresas/{item.id}"} for item in companies],
                "persons": [{"id": str(item.id), "title": item.name, "subtitle": item.role_label or item.email, "href": f"/crm/pessoas/{item.id}"} for item in persons],
                "leads": [{"id": str(item.id), "title": item.company_name, "subtitle": getattr(item.status, "value", item.status), "href": f"/oportunidades/{item.id}"} for item in visible_leads],
                "opportunities": [{"id": str(item.id), "title": item.offer_key, "subtitle": f"Score {item.score}", "href": f"/oportunidades/360/{item.id}"} for item in opportunities],
                "campaigns": [{"id": str(item.id), "title": item.name, "subtitle": "Campanha", "href": f"/campanhas/{item.id}"} for item in campaigns],
            },
        }

    def list_saved_views(self, view_kind: str | None = None) -> list[CommercialSavedView]:
        query = self.db.query(CommercialSavedView).filter(
            CommercialSavedView.organization_id == self.organization_id,
            or_(CommercialSavedView.owner_user_id == self.user.id, CommercialSavedView.shared.is_(True)),
        )
        if view_kind:
            if view_kind not in SAVED_VIEW_KINDS:
                raise SalesOperatingValidation("view_kind inválido")
            query = query.filter(CommercialSavedView.view_kind == view_kind)
        return query.order_by(CommercialSavedView.shared.desc(), CommercialSavedView.name.asc(), CommercialSavedView.id.asc()).all()

    def create_saved_view(self, *, name: str, view_kind: str, filters: dict[str, Any], shared: bool) -> CommercialSavedView:
        name = (name or "").strip()
        if not 2 <= len(name) <= 120:
            raise SalesOperatingValidation("Nome deve ter entre 2 e 120 caracteres")
        if view_kind not in SAVED_VIEW_KINDS:
            raise SalesOperatingValidation("view_kind inválido")
        if shared and not is_full_access(self.member):
            raise SalesOperatingForbidden("Somente gestores podem compartilhar uma visão com o workspace")
        item = CommercialSavedView(
            organization_id=self.organization_id,
            owner_user_id=self.user.id,
            name=name,
            view_kind=view_kind,
            filters=normalize_saved_filters(filters),
            shared=bool(shared),
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_saved_view(self, view_id: Any) -> None:
        try:
            parsed = view_id if isinstance(view_id, uuid.UUID) else uuid.UUID(str(view_id))
        except (TypeError, ValueError) as exc:
            raise SalesOperatingValidation("view_id inválido") from exc
        item = self.db.query(CommercialSavedView).filter(
            CommercialSavedView.id == parsed,
            CommercialSavedView.organization_id == self.organization_id,
        ).first()
        if item is None:
            raise SalesOperatingValidation("Visão não encontrada")
        if item.owner_user_id != self.user.id and not is_full_access(self.member):
            raise SalesOperatingForbidden("Você não pode remover esta visão")
        self.db.delete(item)
        self.db.commit()


def serialize_saved_view(item: CommercialSavedView, current_user_id: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "name": item.name,
        "view_kind": item.view_kind,
        "filters": item.filters or {},
        "shared": bool(item.shared),
        "owner_user_id": str(item.owner_user_id),
        "editable": item.owner_user_id == current_user_id,
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
    }
