"""Automação contínua sobre dados já persistidos.

A execução é org-scoped, idempotente por fingerprint e não chama providers
externos diretamente. Providers continuam sob as quotas e schedulers já
existentes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.db.models import Lead, LeadOpportunityRow, Organization, Person
from database.phase56_models import ProspectingAgentState, ProspectingAlert, SavedProspectingSearch
from services.prospecting.offer_excellence_service import EventSeriesService


AGENT_STATES = {
    "DISCOVERED",
    "NEEDS_ENRICHMENT",
    "READY_TO_SCORE",
    "READY_FOR_CONTACT",
    "AWAITING_ACTION",
    "IN_SEQUENCE",
    "WAITING",
    "REENGAGE",
    "CLOSED",
}


def _fingerprint(*parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def serialize_saved_search(row: SavedProspectingSearch) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "name": row.name,
        "offer_key": row.offer_key,
        "filters": row.filters or {},
        "schedule": row.schedule,
        "notification_policy": row.notification_policy or {},
        "enabled": bool(row.enabled),
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
        "next_run_at": row.next_run_at.isoformat() if row.next_run_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_alert(row: ProspectingAlert) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "saved_search_id": str(row.saved_search_id) if row.saved_search_id else None,
        "lead_id": str(row.lead_id) if row.lead_id else None,
        "event_id": str(row.event_id) if row.event_id else None,
        "kind": row.kind,
        "title": row.title,
        "reason": row.reason,
        "score": row.score,
        "evidence": row.evidence,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


class SavedSearchService:
    def __init__(self, db: Session, organization_id: Any):
        self.db = db
        self.organization_id = organization_id

    def list(self) -> list[dict[str, Any]]:
        rows = (
            self.db.query(SavedProspectingSearch)
            .filter(SavedProspectingSearch.organization_id == self.organization_id)
            .order_by(SavedProspectingSearch.created_at.desc())
            .all()
        )
        return [serialize_saved_search(row) for row in rows]

    def create(
        self,
        *,
        owner_user_id: Any,
        name: str,
        offer_key: str | None,
        filters: dict[str, Any],
        schedule: str,
        notification_policy: dict[str, Any],
    ) -> SavedProspectingSearch:
        row = SavedProspectingSearch(
            organization_id=self.organization_id,
            owner_user_id=owner_user_id,
            name=name.strip(),
            offer_key=(offer_key or "").strip() or None,
            filters=filters,
            schedule=schedule,
            notification_policy=notification_policy,
            enabled=True,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update(self, search_id: Any, **changes: Any) -> SavedProspectingSearch | None:
        row = self._row(search_id)
        if row is None:
            return None
        for key in ("name", "offer_key", "filters", "schedule", "notification_policy", "enabled"):
            if key in changes and changes[key] is not None:
                setattr(row, key, changes[key])
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, search_id: Any) -> bool:
        row = self._row(search_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def _row(self, search_id: Any) -> SavedProspectingSearch | None:
        return (
            self.db.query(SavedProspectingSearch)
            .filter(
                SavedProspectingSearch.id == search_id,
                SavedProspectingSearch.organization_id == self.organization_id,
            )
            .first()
        )

    def _lead_query(self, row: SavedProspectingSearch):
        filters = row.filters if isinstance(row.filters, dict) else {}
        query = self.db.query(Lead).filter(Lead.organization_id == self.organization_id)

        q = str(filters.get("q") or "").strip()
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Lead.company_name.ilike(like), Lead.website.ilike(like)))
        city = str(filters.get("city") or "").strip()
        if city:
            query = query.filter(Lead.city.ilike(city))
        state = str(filters.get("state") or "").strip()
        if state:
            query = query.filter(Lead.state.ilike(state))
        status = str(filters.get("status") or "").strip()
        if status:
            query = query.filter(Lead.status == status)
        if filters.get("has_email") is True:
            query = query.filter(Lead.email.isnot(None))
        if filters.get("has_phone") is True:
            query = query.filter(or_(Lead.phone.isnot(None), Lead.whatsapp.isnot(None)))
        if filters.get("has_website") is False:
            query = query.filter(or_(Lead.website.is_(None), Lead.website == ""))
        if filters.get("has_website") is True:
            query = query.filter(and_(Lead.website.isnot(None), Lead.website != ""))
        return query

    def preview(self, row: SavedProspectingSearch, *, limit: int = 50) -> list[dict[str, Any]]:
        leads = self._lead_query(row).order_by(Lead.updated_at.desc().nullslast(), Lead.created_at.desc()).limit(limit).all()
        result: list[dict[str, Any]] = []
        min_score = float((row.filters or {}).get("min_score") or 0)
        for lead in leads:
            opportunity = None
            offer_key = row.offer_key or str((row.filters or {}).get("offer_key") or "").strip() or None
            oq = self.db.query(LeadOpportunityRow).filter(
                LeadOpportunityRow.organization_id == self.organization_id,
                LeadOpportunityRow.lead_id == lead.id,
            )
            if offer_key:
                oq = oq.filter(LeadOpportunityRow.offer_key == offer_key)
            opportunity = oq.order_by(LeadOpportunityRow.score.desc()).first()
            score = float(opportunity.score or 0) if opportunity else float(lead.qualification_score or 0)
            if score < min_score:
                continue
            result.append({
                "lead_id": str(lead.id),
                "company_name": lead.company_name,
                "city": lead.city,
                "state": lead.state,
                "status": lead.status.value if hasattr(lead.status, "value") else str(lead.status),
                "score": score,
                "offer_key": opportunity.offer_key if opportunity else offer_key,
                "email": lead.email,
                "phone": lead.phone or lead.whatsapp,
            })
        return result

    def run(self, row: SavedProspectingSearch, *, limit: int = 100) -> dict[str, Any]:
        matches = self.preview(row, limit=limit)
        created = 0
        now = datetime.now(timezone.utc)
        for match in matches:
            fp = _fingerprint("saved_search", row.id, match["lead_id"], match.get("offer_key"), round(match["score"], 2))
            existing = self.db.query(ProspectingAlert).filter(
                ProspectingAlert.organization_id == self.organization_id,
                ProspectingAlert.fingerprint == fp,
            ).first()
            if existing:
                continue
            alert = ProspectingAlert(
                organization_id=self.organization_id,
                saved_search_id=row.id,
                lead_id=match["lead_id"],
                kind="saved_search_match",
                title=f"Novo match: {match['company_name']}",
                reason=f"A empresa atende aos filtros de {row.name}.",
                score=match["score"],
                evidence={"filters": row.filters, "offer_key": match.get("offer_key")},
                fingerprint=fp,
            )
            self.db.add(alert)
            created += 1
        row.last_run_at = now
        self.db.commit()
        return {"matches": matches, "created_alerts": created, "ran_at": now.isoformat()}


class AlertService:
    def __init__(self, db: Session, organization_id: Any):
        self.db = db
        self.organization_id = organization_id

    def list(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = self.db.query(ProspectingAlert).filter(ProspectingAlert.organization_id == self.organization_id)
        if status:
            query = query.filter(ProspectingAlert.status == status)
        rows = query.order_by(ProspectingAlert.created_at.desc()).limit(limit).all()
        return [serialize_alert(row) for row in rows]

    def set_status(self, alert_id: Any, status: str) -> ProspectingAlert | None:
        if status not in {"new", "read", "dismissed", "actioned"}:
            raise ValueError("status de alerta inválido")
        row = self.db.query(ProspectingAlert).filter(
            ProspectingAlert.id == alert_id,
            ProspectingAlert.organization_id == self.organization_id,
        ).first()
        if row is None:
            return None
        row.status = status
        self.db.commit()
        self.db.refresh(row)
        return row

    def materialize_rebuy_alerts(self) -> int:
        EventSeriesService.rebuild(self.db, self.organization_id)
        candidates = EventSeriesService.rebuy_candidates(self.db, self.organization_id)
        created = 0
        for item in candidates:
            fp = _fingerprint("event_rebuy", item["series_id"], item["expected_next_window"])
            exists = self.db.query(ProspectingAlert).filter(
                ProspectingAlert.organization_id == self.organization_id,
                ProspectingAlert.fingerprint == fp,
            ).first()
            if exists:
                continue
            row = ProspectingAlert(
                organization_id=self.organization_id,
                event_id=item.get("latest_event_id"),
                kind="event_rebuy",
                title=f"Janela de recompra: {item['name']}",
                reason="A série recorrente entrou na janela comercial de 30 a 120 dias.",
                score=float(item["recurrence_confidence"] * 100),
                evidence=item,
                fingerprint=fp,
            )
            self.db.add(row)
            created += 1
        self.db.commit()
        return created


class AgentStateService:
    def __init__(self, db: Session, organization_id: Any):
        self.db = db
        self.organization_id = organization_id

    def derive(self, lead: Lead) -> tuple[str, str, dict[str, Any]]:
        status = lead.status.value if hasattr(lead.status, "value") else str(lead.status or "")
        terminal = status.upper() in {"CONVERTIDO", "PERDIDO", "DESQUALIFICADO", "WON", "LOST", "DISQUALIFIED"}
        if terminal:
            return "CLOSED", f"status_terminal:{status}", {"lead_status": status}

        opportunity = self.db.query(LeadOpportunityRow).filter(
            LeadOpportunityRow.organization_id == self.organization_id,
            LeadOpportunityRow.lead_id == lead.id,
        ).order_by(LeadOpportunityRow.score.desc()).first()
        if opportunity is None:
            has_enrichment = bool(getattr(lead, "last_enriched_at", None) or getattr(lead, "evidence_score", None))
            return (
                ("READY_TO_SCORE", "enrichment_disponivel", {})
                if has_enrichment
                else ("NEEDS_ENRICHMENT", "sem_oportunidade_persistida", {})
            )

        person = None
        if lead.primary_person_id:
            person = self.db.query(Person).filter(
                Person.organization_id == self.organization_id,
                Person.id == lead.primary_person_id,
            ).first()
        if person and bool(person.routable):
            if getattr(lead, "next_action_at", None):
                return "AWAITING_ACTION", "contato_roteavel_com_proxima_acao", {"score": opportunity.score}
            return "READY_FOR_CONTACT", "contato_roteavel", {"score": opportunity.score}

        if status.upper() in {"CONTATADO", "CONTACTED", "EM_CONTATO"}:
            return "WAITING", "contato_iniciado", {"score": opportunity.score}
        if status.upper() in {"RESPONDIDO", "RESPONDEU", "RESPONDED", "NEGOCIANDO"}:
            return "AWAITING_ACTION", "resposta_recebida", {"score": opportunity.score}
        return "READY_FOR_CONTACT", "oportunidade_sem_contato_roteavel", {"score": opportunity.score, "needs_contact_resolution": True}

    def refresh(self, lead: Lead) -> ProspectingAgentState:
        state, reason, evidence = self.derive(lead)
        if state not in AGENT_STATES:
            raise ValueError("estado inválido")
        row = self.db.query(ProspectingAgentState).filter(
            ProspectingAgentState.organization_id == self.organization_id,
            ProspectingAgentState.lead_id == lead.id,
        ).first()
        now = datetime.now(timezone.utc)
        if row is None:
            row = ProspectingAgentState(
                organization_id=self.organization_id,
                lead_id=lead.id,
                state=state,
                reason=reason,
                evidence=evidence,
                history=[{"state": state, "reason": reason, "at": now.isoformat()}],
                changed_at=now,
            )
            self.db.add(row)
        elif row.state != state or row.reason != reason:
            history = list(row.history or [])
            history.append({"state": state, "reason": reason, "at": now.isoformat()})
            row.history = history[-50:]
            row.state = state
            row.reason = reason
            row.evidence = evidence
            row.changed_at = now
        else:
            row.evidence = evidence
        self.db.commit()
        self.db.refresh(row)
        return row

    def refresh_all(self, *, limit: int = 250) -> dict[str, int]:
        leads = self.db.query(Lead).filter(Lead.organization_id == self.organization_id).order_by(Lead.updated_at.desc().nullslast()).limit(limit).all()
        counts: dict[str, int] = {}
        for lead in leads:
            row = self.refresh(lead)
            counts[row.state] = counts.get(row.state, 0) + 1
        return counts
