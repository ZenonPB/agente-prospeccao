"""Composição read-only da visão comercial de uma oportunidade.

A visão agrega apenas dados já persistidos. Leituras relacionadas permanecem
confinadas ao workspace ativo e são feitas em lotes fixos para evitar N+1.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from database.engagement_models import (
    CommercialTask,
    NextBestActionDecision,
    SequenceEnrollment,
    SequenceExecution,
    WorkflowRun,
)
from src.db.models import (
    CommercialOutcomeRow,
    Contact,
    Enrichment,
    Lead,
    LeadActivity,
    LeadOpportunityRow,
    LeadUsefulnessFeedback,
    User,
)
from src.services.org_service import consultant_lead_scope


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _timeline_timestamp(item: dict[str, Any]) -> float:
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


def sort_timeline(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mais recentes primeiro, com desempate estável e determinístico."""
    return sorted(
        items,
        key=lambda item: (
            -_timeline_timestamp(item),
            str(item.get("type") or ""),
            str(item.get("source_entity") or ""),
        ),
    )


class Opportunity360Service:
    """Monta a leitura 360 sem criar novas fontes de verdade comerciais."""

    def __init__(self, db: Session, organization_id: Any, member: Any | None = None):
        self.db = db
        self.organization_id = organization_id
        self.member = member

    def get(self, opportunity_id: Any) -> dict[str, Any] | None:
        opportunity = (
            self.db.query(LeadOpportunityRow)
            .filter(
                LeadOpportunityRow.id == opportunity_id,
                LeadOpportunityRow.organization_id == self.organization_id,
            )
            .first()
        )
        if opportunity is None:
            return None

        lead_query = (
            self.db.query(Lead)
            .filter(
                Lead.id == opportunity.lead_id,
                Lead.organization_id == self.organization_id,
            )
            .options(
                joinedload(Lead.assigned_to),
                joinedload(Lead.company),
                joinedload(Lead.primary_person),
            )
        )
        if self.member is not None:
            lead_query = consultant_lead_scope(self.member, lead_query)
        lead = lead_query.first()
        if lead is None:
            return None

        contacts = (
            self.db.query(Contact)
            .filter(Contact.lead_id == lead.id)
            .order_by(Contact.is_primary.desc(), Contact.confidence.desc(), Contact.created_at.asc())
            .all()
        )
        activities = (
            self.db.query(LeadActivity)
            .filter(LeadActivity.lead_id == lead.id)
            .order_by(LeadActivity.created_at.desc(), LeadActivity.id.asc())
            .all()
        )
        tasks = (
            self.db.query(CommercialTask)
            .filter(
                CommercialTask.organization_id == self.organization_id,
                CommercialTask.lead_id == lead.id,
            )
            .order_by(CommercialTask.due_at.asc().nullslast(), CommercialTask.created_at.desc())
            .all()
        )
        feedbacks = (
            self.db.query(LeadUsefulnessFeedback)
            .filter(
                LeadUsefulnessFeedback.organization_id == self.organization_id,
                LeadUsefulnessFeedback.lead_id == lead.id,
            )
            .order_by(LeadUsefulnessFeedback.updated_at.desc(), LeadUsefulnessFeedback.created_at.desc())
            .all()
        )
        outcomes = (
            self.db.query(CommercialOutcomeRow)
            .filter(
                CommercialOutcomeRow.organization_id == self.organization_id,
                CommercialOutcomeRow.lead_id == lead.id,
                CommercialOutcomeRow.lead_opportunity_id == opportunity.id,
            )
            .order_by(CommercialOutcomeRow.recorded_at.desc())
            .all()
        )
        decisions = (
            self.db.query(NextBestActionDecision)
            .filter(
                NextBestActionDecision.organization_id == self.organization_id,
                NextBestActionDecision.lead_id == lead.id,
                or_(
                    NextBestActionDecision.offer_key == opportunity.offer_key,
                    NextBestActionDecision.offer_key.is_(None),
                ),
            )
            .order_by(NextBestActionDecision.created_at.desc())
            .all()
        )
        enrollments = (
            self.db.query(SequenceEnrollment)
            .filter(
                SequenceEnrollment.organization_id == self.organization_id,
                SequenceEnrollment.lead_id == lead.id,
            )
            .order_by(SequenceEnrollment.created_at.desc())
            .all()
        )
        executions = (
            self.db.query(SequenceExecution)
            .filter(
                SequenceExecution.organization_id == self.organization_id,
                SequenceExecution.lead_id == lead.id,
            )
            .order_by(SequenceExecution.created_at.desc())
            .all()
        )
        workflow_runs = (
            self.db.query(WorkflowRun)
            .filter(
                WorkflowRun.organization_id == self.organization_id,
                WorkflowRun.entity_id.in_([str(lead.id), str(opportunity.id)]),
            )
            .order_by(WorkflowRun.started_at.desc())
            .all()
        )
        enrichment = (
            self.db.query(Enrichment)
            .filter(Enrichment.lead_id == lead.id)
            .order_by(Enrichment.created_at.desc())
            .first()
        )

        user_ids = {
            value
            for value in [
                *(getattr(item, "user_id", None) for item in activities),
                *(getattr(item, "owner_user_id", None) for item in tasks),
                *(getattr(item, "user_id", None) for item in feedbacks),
            ]
            if value is not None
        }
        users = (
            self.db.query(User).filter(User.id.in_(user_ids)).all()
            if user_ids
            else []
        )
        users_by_id = {str(user.id): user for user in users}

        score_vector = _as_dict(getattr(lead, "score_vector", None))
        qualification = {
            "icp_fit": score_vector.get("icp_fit"),
            "need": score_vector.get("need"),
            "intent": score_vector.get("intent"),
            "buying_power": score_vector.get("buying_power"),
            "reachability": score_vector.get("reachability"),
            "timing": score_vector.get("timing"),
            "commercial_fit": score_vector.get("commercial_fit"),
            "coverage": score_vector.get("coverage"),
            "overall": score_vector.get("overall"),
        }

        serialized_tasks = [self._task(item, users_by_id) for item in tasks]
        serialized_activities = [self._activity(item, users_by_id) for item in activities]
        serialized_feedbacks = [self._feedback(item, users_by_id) for item in feedbacks]
        serialized_outcomes = [self._outcome(item) for item in outcomes]
        serialized_executions = [self._execution(item) for item in executions]
        serialized_workflows = [self._workflow(item) for item in workflow_runs]

        exact_decisions = [item for item in decisions if item.offer_key == opportunity.offer_key]
        next_decision = (exact_decisions or decisions or [None])[0]
        next_action = self._next_action(next_decision, lead)

        timeline: list[dict[str, Any]] = []
        timeline.extend(self._activity_timeline(item) for item in serialized_activities)
        timeline.extend(self._task_timeline(item) for item in serialized_tasks)
        timeline.extend(self._feedback_timeline(item) for item in serialized_feedbacks)
        timeline.extend(self._outcome_timeline(item) for item in serialized_outcomes)
        timeline.extend(self._execution_timeline(item) for item in serialized_executions)
        timeline.extend(self._workflow_timeline(item) for item in serialized_workflows)
        if next_action and next_action.get("created_at"):
            timeline.append({
                "type": "NEXT_ACTION",
                "occurred_at": next_action["created_at"],
                "actor": None,
                "title": "Próxima ação recomendada",
                "description": next_action.get("why"),
                "source_entity": f"next_best_action:{next_action.get('id') or 'derived'}",
                "metadata": {
                    "action": next_action.get("action"),
                    "confidence": next_action.get("confidence"),
                    "deadline": next_action.get("deadline"),
                    "status": next_action.get("status"),
                },
            })

        return {
            "opportunity": self._opportunity(opportunity),
            "lead": self._lead(lead),
            "company": self._company(lead),
            "decision_maker": self._decision_maker(lead, contacts),
            "contacts": [self._contact(item) for item in contacts],
            "qualification": qualification,
            "enrichment": self._enrichment(enrichment),
            "commercial": {
                "status": _enum_value(lead.status),
                "negotiation_stage": _enum_value(getattr(lead, "negotiation_stage", None)),
                "contract_outcome": _enum_value(getattr(lead, "contract_outcome", None)),
                "value": float(lead.value) if getattr(lead, "value", None) is not None else None,
                "expected_close_date": _iso(getattr(lead, "expected_close_date", None)),
                "outcome_date": _iso(getattr(lead, "outcome_date", None)),
                "lost_reason": _enum_value(getattr(lead, "lost_reason", None)),
            },
            "owner": self._owner(lead),
            "next_action": next_action,
            "tasks": serialized_tasks,
            "activities": serialized_activities,
            "usefulness_feedback": serialized_feedbacks,
            "outcomes": serialized_outcomes,
            "engagement": {
                "enrollments": [self._enrollment(item) for item in enrollments],
                "executions": serialized_executions,
                "workflow_runs": serialized_workflows,
            },
            "timeline": sort_timeline(timeline),
            "capabilities": {
                "proposal_entity": False,
                "contract_entity": False,
                "notes_entity": False,
                "read_only": True,
            },
        }

    @staticmethod
    def _opportunity(item: LeadOpportunityRow) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "lead_id": str(item.lead_id),
            "offer_key": item.offer_key,
            "offer_version": item.offer_version,
            "profile_key": item.profile_key,
            "score": item.score,
            "resolved_from": item.resolved_from,
            "signals_matched": _as_list(item.signals_matched),
            "signals_missing": _as_list(item.signals_missing),
            "evidence": _as_list(item.evidence),
            "score_breakdown": _as_dict(getattr(item, "score_breakdown", None)),
            "created_at": _iso(item.created_at),
            "updated_at": _iso(item.updated_at),
        }

    @staticmethod
    def _lead(lead: Lead) -> dict[str, Any]:
        return {
            "id": str(lead.id),
            "company_name": lead.company_name,
            "category": lead.category,
            "city": lead.city,
            "state": lead.state,
            "country": lead.country,
            "website": lead.website,
            "cnpj": lead.cnpj,
            "qualification_score": lead.qualification_score,
            "qualification_reason": lead.qualification_reason,
            "priority": _enum_value(lead.priority),
            "primary_need": lead.primary_need,
            "notes": lead.notes,
            "next_action_at": _iso(lead.next_action_at),
            "last_contacted_at": _iso(lead.last_contacted_at),
            "campaign_id": str(lead.campaign_id) if lead.campaign_id else None,
            "created_at": _iso(lead.created_at),
            "updated_at": _iso(lead.updated_at),
        }

    @staticmethod
    def _company(lead: Lead) -> dict[str, Any]:
        company = getattr(lead, "company", None)
        return {
            "id": str(company.id) if company is not None else None,
            "name": getattr(company, "company_name", None) or lead.company_name,
            "cnpj": getattr(company, "cnpj", None) or lead.cnpj,
            "domain": getattr(company, "normalized_domain", None) or getattr(lead, "normalized_domain", None),
            "website": getattr(company, "website", None) or lead.website,
            "city": getattr(company, "city", None) or lead.city,
            "state": getattr(company, "state", None) or lead.state,
            "country": getattr(company, "country", None) or lead.country,
            "industry": getattr(company, "industry", None) or lead.category,
            "source": getattr(company, "source", None),
        }

    @staticmethod
    def _decision_maker(lead: Lead, contacts: list[Contact]) -> dict[str, Any] | None:
        person = getattr(lead, "primary_person", None)
        if person is not None:
            return {
                "person_id": str(person.id),
                "name": getattr(person, "name", None),
                "title": getattr(person, "title", None),
                "seniority": getattr(person, "seniority", None),
                "department": getattr(person, "department", None),
                "buyer_role": getattr(person, "buyer_role", None),
                "email": getattr(person, "email", None),
                "phone": getattr(person, "phone", None),
                "linkedin_url": getattr(person, "linkedin_url", None),
                "identity_confidence": getattr(person, "identity_confidence", None),
                "contact_confidence": getattr(person, "contact_confidence", None),
            }
        primary = next((item for item in contacts if item.is_primary), None)
        if primary is None:
            return None
        return {
            "person_id": None,
            "contact_id": str(primary.id),
            "name": primary.name,
            "title": primary.role_label,
            "seniority": None,
            "department": None,
            "buyer_role": _enum_value(primary.role),
            "email": primary.email,
            "phone": primary.phone,
            "linkedin_url": primary.linkedin_url,
            "identity_confidence": getattr(primary, "identity_confidence", None),
            "contact_confidence": getattr(primary, "contact_confidence", None),
        }

    @staticmethod
    def _contact(item: Contact) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "name": item.name,
            "role": _enum_value(item.role),
            "role_label": item.role_label,
            "email": item.email,
            "email_verified": bool(getattr(item, "email_verified", False)),
            "phone": item.phone,
            "linkedin_url": item.linkedin_url,
            "is_primary": bool(item.is_primary),
            "identity_confidence": getattr(item, "identity_confidence", None),
            "contact_confidence": getattr(item, "contact_confidence", None),
            "verification_status": getattr(item, "verification_status", None),
            "routability_type": getattr(item, "routability_type", None),
            "routable": bool(getattr(item, "routable", False)),
            "source": item.source,
        }

    @staticmethod
    def _owner(lead: Lead) -> dict[str, Any] | None:
        user = getattr(lead, "assigned_to", None)
        if user is None:
            return None
        return {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "assigned_at": _iso(lead.assigned_at),
        }

    @staticmethod
    def _task(item: CommercialTask, users: dict[str, User]) -> dict[str, Any]:
        owner = users.get(str(item.owner_user_id)) if item.owner_user_id else None
        return {
            "id": str(item.id),
            "task_type": item.task_type,
            "title": item.title,
            "description": item.description,
            "status": item.status,
            "source": item.source,
            "due_at": _iso(item.due_at),
            "completed_at": _iso(item.completed_at),
            "created_at": _iso(item.created_at),
            "updated_at": _iso(item.updated_at),
            "owner": {"id": str(owner.id), "name": owner.name} if owner else None,
        }

    @staticmethod
    def _activity(item: LeadActivity, users: dict[str, User]) -> dict[str, Any]:
        actor = users.get(str(item.user_id)) if item.user_id else None
        return {
            "id": str(item.id),
            "action": _enum_value(item.action),
            "actor": {"id": str(actor.id), "name": actor.name} if actor else None,
            "status_from": _enum_value(item.status_from),
            "status_to": _enum_value(item.status_to),
            "detail": item.detail,
            "created_at": _iso(item.created_at),
        }

    @staticmethod
    def _feedback(item: LeadUsefulnessFeedback, users: dict[str, User]) -> dict[str, Any]:
        actor = users.get(str(item.user_id)) if item.user_id else None
        return {
            "id": str(item.id),
            "useful": bool(item.useful),
            "reason": _enum_value(item.reason),
            "detail": item.detail,
            "actor": {"id": str(actor.id), "name": actor.name} if actor else None,
            "created_at": _iso(getattr(item, "created_at", None)),
            "updated_at": _iso(getattr(item, "updated_at", None)),
        }

    @staticmethod
    def _outcome(item: CommercialOutcomeRow) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "outcome": item.outcome,
            "value": float(item.value or 0),
            "provider": item.provider,
            "event_key": item.event_key,
            "outreach_at": _iso(item.outreach_at),
            "recorded_at": _iso(item.recorded_at),
        }

    @staticmethod
    def _enrollment(item: SequenceEnrollment) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "sequence_id": str(item.sequence_id),
            "status": item.status,
            "current_step_index": item.current_step_index,
            "next_action_at": _iso(item.next_action_at),
            "last_action_at": _iso(item.last_action_at),
            "created_at": _iso(item.created_at),
        }

    @staticmethod
    def _execution(item: SequenceExecution) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "enrollment_id": str(item.enrollment_id),
            "step_index": item.step_index,
            "step_type": item.step_type,
            "status": item.status,
            "scheduled_at": _iso(item.scheduled_at),
            "ready_at": _iso(item.ready_at),
            "completed_at": _iso(item.completed_at),
            "created_at": _iso(item.created_at),
        }

    @staticmethod
    def _workflow(item: WorkflowRun) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "workflow_id": str(item.workflow_id),
            "trigger_type": item.trigger_type,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "status": item.status,
            "started_at": _iso(item.started_at),
            "completed_at": _iso(item.completed_at),
        }

    @staticmethod
    def _enrichment(item: Enrichment | None) -> dict[str, Any] | None:
        if item is None:
            return None
        return {
            "website_exists": item.website_exists,
            "responsive_design": item.responsive_design,
            "cms": item.cms,
            "lighthouse_score": item.lighthouse_score,
            "load_time_ms": item.load_time_ms,
            "created_at": _iso(item.created_at),
        }

    @staticmethod
    def _next_action(item: NextBestActionDecision | None, lead: Lead) -> dict[str, Any] | None:
        if item is not None:
            return {
                "id": str(item.id),
                "action": item.action,
                "why": item.why,
                "confidence": item.confidence,
                "evidence": _as_list(item.evidence),
                "deadline": _iso(item.deadline),
                "status": item.status,
                "offer_key": item.offer_key,
                "created_at": _iso(item.created_at),
            }
        if lead.next_action_at:
            return {
                "id": None,
                "action": "FOLLOW_UP",
                "why": "Próxima ação agendada no CRM",
                "confidence": None,
                "evidence": [],
                "deadline": _iso(lead.next_action_at),
                "status": "SCHEDULED",
                "offer_key": None,
                "created_at": _iso(lead.updated_at or lead.created_at),
            }
        return None

    @staticmethod
    def _activity_timeline(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "ACTIVITY",
            "occurred_at": item.get("created_at"),
            "actor": item.get("actor"),
            "title": "Atividade comercial",
            "description": item.get("detail"),
            "source_entity": f"lead_activity:{item['id']}",
            "metadata": {
                "action": item.get("action"),
                "status_from": item.get("status_from"),
                "status_to": item.get("status_to"),
            },
        }

    @staticmethod
    def _task_timeline(item: dict[str, Any]) -> dict[str, Any]:
        occurred_at = item.get("completed_at") or item.get("updated_at") or item.get("created_at")
        return {
            "type": "TASK",
            "occurred_at": occurred_at,
            "actor": item.get("owner"),
            "title": item.get("title") or "Tarefa comercial",
            "description": item.get("description"),
            "source_entity": f"commercial_task:{item['id']}",
            "metadata": {
                "task_type": item.get("task_type"),
                "status": item.get("status"),
                "due_at": item.get("due_at"),
            },
        }

    @staticmethod
    def _feedback_timeline(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "FEEDBACK",
            "occurred_at": item.get("updated_at") or item.get("created_at"),
            "actor": item.get("actor"),
            "title": "Lead avaliado como útil" if item.get("useful") else "Lead avaliado como não útil",
            "description": item.get("detail"),
            "source_entity": f"lead_usefulness_feedback:{item['id']}",
            "metadata": {"useful": item.get("useful"), "reason": item.get("reason")},
        }

    @staticmethod
    def _outcome_timeline(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "OUTCOME",
            "occurred_at": item.get("recorded_at"),
            "actor": None,
            "title": "Resultado comercial registrado",
            "description": item.get("outcome"),
            "source_entity": f"commercial_outcome:{item['id']}",
            "metadata": {"outcome": item.get("outcome"), "value": item.get("value")},
        }

    @staticmethod
    def _execution_timeline(item: dict[str, Any]) -> dict[str, Any]:
        occurred_at = item.get("completed_at") or item.get("ready_at") or item.get("scheduled_at") or item.get("created_at")
        return {
            "type": "SEQUENCE",
            "occurred_at": occurred_at,
            "actor": None,
            "title": "Etapa de sequência comercial",
            "description": item.get("step_type"),
            "source_entity": f"sequence_execution:{item['id']}",
            "metadata": {
                "step_type": item.get("step_type"),
                "status": item.get("status"),
                "step_index": item.get("step_index"),
            },
        }

    @staticmethod
    def _workflow_timeline(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "WORKFLOW",
            "occurred_at": item.get("completed_at") or item.get("started_at"),
            "actor": None,
            "title": "Automação comercial",
            "description": item.get("trigger_type"),
            "source_entity": f"workflow_run:{item['id']}",
            "metadata": {"status": item.get("status"), "trigger_type": item.get("trigger_type")},
        }
