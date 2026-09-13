"""Visões 360 read-only das entidades canônicas de CRM.

Company e Person permanecem fontes canônicas independentes de campanha. A
composição é org-scoped, respeita o escopo de carteira do membro e consulta
relações em lotes para não introduzir N+1.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from database.engagement_models import CommercialTask
from src.db.models import (
    CommercialOutcomeRow,
    Company,
    CompanyAlias,
    Lead,
    LeadActivity,
    LeadOpportunityRow,
    Person,
)
from src.services.org_service import consultant_lead_scope


def _enum(value: Any) -> Any:
    return getattr(value, "value", value)


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _timeline_ts(item: dict[str, Any]) -> float:
    raw = item.get("occurred_at")
    if not raw:
        return float("-inf")
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError):
        return float("-inf")


def _sort_timeline(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            -_timeline_ts(item),
            str(item.get("type") or ""),
            str(item.get("source_entity") or ""),
        ),
    )


class Crm360Service:
    def __init__(self, db, organization_id: Any, member: Any | None = None):
        self.db = db
        self.organization_id = organization_id
        self.member = member

    def _visible_leads(self, *, company_id: Any | None = None):
        query = self.db.query(Lead).filter(Lead.organization_id == self.organization_id)
        if company_id is not None:
            query = query.filter(Lead.company_id == company_id)
        if self.member is not None:
            query = consultant_lead_scope(self.member, query)
        return query

    def company(self, company_id: Any) -> dict[str, Any] | None:
        company = self.db.query(Company).filter(
            Company.id == company_id,
            Company.organization_id == self.organization_id,
        ).first()
        if company is None:
            return None

        leads = self._visible_leads(company_id=company.id).order_by(Lead.created_at.desc()).all()
        # CONSULTOR não usa Company 360 para inferir contas de outra carteira.
        if self.member is not None and not leads:
            return None
        lead_ids = [lead.id for lead in leads]

        persons = self.db.query(Person).filter(
            Person.organization_id == self.organization_id,
            Person.company_id == company.id,
        ).order_by(Person.name.asc(), Person.id.asc()).all()
        aliases = self.db.query(CompanyAlias).filter(
            CompanyAlias.organization_id == self.organization_id,
            CompanyAlias.company_id == company.id,
        ).order_by(CompanyAlias.alias_kind.asc(), CompanyAlias.created_at.asc()).all()

        opportunities = []
        activities = []
        tasks = []
        outcomes = []
        if lead_ids:
            opportunities = self.db.query(LeadOpportunityRow).filter(
                LeadOpportunityRow.organization_id == self.organization_id,
                LeadOpportunityRow.lead_id.in_(lead_ids),
            ).order_by(LeadOpportunityRow.score.desc(), LeadOpportunityRow.created_at.desc()).all()
            activities = self.db.query(LeadActivity).filter(
                LeadActivity.lead_id.in_(lead_ids),
            ).order_by(LeadActivity.created_at.desc(), LeadActivity.id.asc()).limit(250).all()
            tasks = self.db.query(CommercialTask).filter(
                CommercialTask.organization_id == self.organization_id,
                CommercialTask.lead_id.in_(lead_ids),
            ).order_by(CommercialTask.due_at.asc().nullslast(), CommercialTask.created_at.desc()).all()
            outcomes = self.db.query(CommercialOutcomeRow).filter(
                CommercialOutcomeRow.organization_id == self.organization_id,
                CommercialOutcomeRow.lead_id.in_(lead_ids),
            ).order_by(CommercialOutcomeRow.recorded_at.desc()).all()

        lead_by_id = {str(item.id): item for item in leads}
        timeline = self._timeline(activities, tasks, outcomes, lead_by_id)
        open_tasks = [item for item in tasks if str(item.status).upper() not in {"COMPLETED", "CANCELLED"}]
        won_value = sum(float(item.value or 0) for item in outcomes if str(item.outcome).upper() == "WON")

        return {
            "company": self._company(company),
            "summary": {
                "lead_count": len(leads),
                "person_count": len(persons),
                "opportunity_count": len(opportunities),
                "open_task_count": len(open_tasks),
                "won_value": won_value,
                "best_opportunity_score": max((item.score for item in opportunities), default=None),
            },
            "persons": [self._person(item) for item in persons],
            "leads": [self._lead(item) for item in leads],
            "opportunities": [self._opportunity(item) for item in opportunities],
            "tasks": [self._task(item) for item in tasks],
            "outcomes": [self._outcome(item) for item in outcomes],
            "aliases": [
                {
                    "kind": item.alias_kind,
                    "value": item.alias_value,
                    "source": item.source,
                    "created_at": _iso(item.created_at),
                }
                for item in aliases
            ],
            "timeline": timeline,
            "capabilities": {"read_only": True, "canonical_company": True},
        }

    def person(self, person_id: Any) -> dict[str, Any] | None:
        person = self.db.query(Person).filter(
            Person.id == person_id,
            Person.organization_id == self.organization_id,
        ).first()
        if person is None:
            return None

        visible_company_leads = []
        if person.company_id is not None:
            visible_company_leads = self._visible_leads(company_id=person.company_id).order_by(Lead.created_at.desc()).all()
            if self.member is not None and not visible_company_leads:
                return None

        primary_leads = [lead for lead in visible_company_leads if lead.primary_person_id == person.id]
        related_leads = primary_leads or visible_company_leads
        lead_ids = [lead.id for lead in related_leads]

        opportunities = []
        tasks = []
        activities = []
        outcomes = []
        if lead_ids:
            opportunities = self.db.query(LeadOpportunityRow).filter(
                LeadOpportunityRow.organization_id == self.organization_id,
                LeadOpportunityRow.lead_id.in_(lead_ids),
            ).order_by(LeadOpportunityRow.score.desc(), LeadOpportunityRow.created_at.desc()).all()
            tasks = self.db.query(CommercialTask).filter(
                CommercialTask.organization_id == self.organization_id,
                CommercialTask.lead_id.in_(lead_ids),
            ).order_by(CommercialTask.due_at.asc().nullslast(), CommercialTask.created_at.desc()).all()
            activities = self.db.query(LeadActivity).filter(
                LeadActivity.lead_id.in_(lead_ids),
            ).order_by(LeadActivity.created_at.desc(), LeadActivity.id.asc()).limit(250).all()
            outcomes = self.db.query(CommercialOutcomeRow).filter(
                CommercialOutcomeRow.organization_id == self.organization_id,
                CommercialOutcomeRow.lead_id.in_(lead_ids),
            ).order_by(CommercialOutcomeRow.recorded_at.desc()).all()

        company = None
        if person.company_id is not None:
            company = self.db.query(Company).filter(
                Company.id == person.company_id,
                Company.organization_id == self.organization_id,
            ).first()

        lead_by_id = {str(item.id): item for item in related_leads}
        return {
            "person": self._person(person),
            "company": self._company(company) if company is not None else None,
            "summary": {
                "primary_on_lead_count": len(primary_leads),
                "related_lead_count": len(related_leads),
                "opportunity_count": len(opportunities),
                "open_task_count": len([
                    item for item in tasks
                    if str(item.status).upper() not in {"COMPLETED", "CANCELLED"}
                ]),
                "best_opportunity_score": max((item.score for item in opportunities), default=None),
            },
            "leads": [self._lead(item) for item in related_leads],
            "opportunities": [self._opportunity(item) for item in opportunities],
            "tasks": [self._task(item) for item in tasks],
            "outcomes": [self._outcome(item) for item in outcomes],
            "timeline": self._timeline(activities, tasks, outcomes, lead_by_id),
            "capabilities": {"read_only": True, "canonical_person": True},
        }

    @staticmethod
    def _company(item: Company) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "company_name": item.company_name,
            "name": item.name,
            "cnpj": item.cnpj,
            "website": item.website,
            "domain": item.normalized_domain,
            "phone": item.phone,
            "address": item.address,
            "city": item.city,
            "state": item.state,
            "country": item.country,
            "category": item.category,
            "google_rating": item.google_rating,
            "google_rating_count": item.google_rating_count,
            "google_maps_uri": item.google_maps_uri,
            "linkedin_url": item.company_linkedin_url,
            "instagram_url": item.instagram_url,
            "created_at": _iso(item.created_at),
            "updated_at": _iso(item.updated_at),
        }

    @staticmethod
    def _person(item: Person) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "company_id": str(item.company_id) if item.company_id else None,
            "name": item.name,
            "role": _enum(item.role),
            "role_label": item.role_label,
            "email": item.email,
            "phone": item.phone,
            "email_verified": bool(item.email_verified),
            "linkedin_url": item.linkedin_url,
            "identity_confidence": item.identity_confidence,
            "contact_confidence": item.contact_confidence,
            "source_reliability": item.source_reliability,
            "verification_status": item.verification_status,
            "last_verified_at": _iso(item.last_verified_at),
            "routability_type": item.routability_type,
            "routable": bool(item.routable),
            "routability_reason": item.routability_reason,
            "source": item.source,
            "created_at": _iso(item.created_at),
            "updated_at": _iso(item.updated_at),
        }

    @staticmethod
    def _lead(item: Lead) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "company_id": str(item.company_id) if item.company_id else None,
            "primary_person_id": str(item.primary_person_id) if item.primary_person_id else None,
            "campaign_id": str(item.campaign_id) if item.campaign_id else None,
            "company_name": item.company_name,
            "status": _enum(item.status),
            "priority": _enum(item.priority),
            "qualification_score": item.qualification_score,
            "value": float(item.value) if item.value is not None else None,
            "expected_close_date": _iso(item.expected_close_date),
            "assigned_to_id": str(item.assigned_to_id) if item.assigned_to_id else None,
            "next_action_at": _iso(item.next_action_at),
            "created_at": _iso(item.created_at),
            "updated_at": _iso(item.updated_at),
        }

    @staticmethod
    def _opportunity(item: LeadOpportunityRow) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "lead_id": str(item.lead_id),
            "offer_key": item.offer_key,
            "offer_version": item.offer_version,
            "score": item.score,
            "signals_matched": item.signals_matched or [],
            "created_at": _iso(item.created_at),
            "updated_at": _iso(item.updated_at),
        }

    @staticmethod
    def _task(item: CommercialTask) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "lead_id": str(item.lead_id),
            "owner_user_id": str(item.owner_user_id) if item.owner_user_id else None,
            "task_type": item.task_type,
            "title": item.title,
            "description": item.description,
            "due_at": _iso(item.due_at),
            "status": item.status,
            "source": item.source,
            "created_at": _iso(item.created_at),
            "completed_at": _iso(item.completed_at),
        }

    @staticmethod
    def _outcome(item: CommercialOutcomeRow) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "lead_id": str(item.lead_id),
            "lead_opportunity_id": str(item.lead_opportunity_id) if item.lead_opportunity_id else None,
            "offer_key": item.offer_key,
            "offer_version": item.offer_version,
            "outcome": item.outcome,
            "value": float(item.value or 0),
            "recorded_at": _iso(item.recorded_at),
        }

    @staticmethod
    def _timeline(activities, tasks, outcomes, lead_by_id) -> list[dict[str, Any]]:
        timeline: list[dict[str, Any]] = []
        for item in activities:
            lead = lead_by_id.get(str(item.lead_id))
            timeline.append({
                "type": "ACTIVITY",
                "occurred_at": _iso(item.created_at),
                "actor": str(item.user_id) if item.user_id else None,
                "title": _enum(item.action) or "Atividade",
                "description": item.detail,
                "source_entity": f"lead_activity:{item.id}",
                "metadata": {
                    "lead_id": str(item.lead_id),
                    "lead_name": lead.company_name if lead else None,
                    "status_from": _enum(item.status_from),
                    "status_to": _enum(item.status_to),
                },
            })
        for item in tasks:
            lead = lead_by_id.get(str(item.lead_id))
            timeline.append({
                "type": "TASK",
                "occurred_at": _iso(item.completed_at or item.created_at),
                "actor": str(item.owner_user_id) if item.owner_user_id else None,
                "title": item.title,
                "description": item.description,
                "source_entity": f"commercial_task:{item.id}",
                "metadata": {
                    "lead_id": str(item.lead_id),
                    "lead_name": lead.company_name if lead else None,
                    "status": item.status,
                    "due_at": _iso(item.due_at),
                    "task_type": item.task_type,
                },
            })
        for item in outcomes:
            lead = lead_by_id.get(str(item.lead_id))
            timeline.append({
                "type": "OUTCOME",
                "occurred_at": _iso(item.recorded_at),
                "actor": None,
                "title": f"Resultado comercial: {item.outcome}",
                "description": None,
                "source_entity": f"commercial_outcome:{item.id}",
                "metadata": {
                    "lead_id": str(item.lead_id),
                    "lead_name": lead.company_name if lead else None,
                    "offer_key": item.offer_key,
                    "offer_version": item.offer_version,
                    "value": float(item.value or 0),
                },
            })
        return _sort_timeline(timeline)
