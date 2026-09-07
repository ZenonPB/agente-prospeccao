"""Persistência das oportunidades descobertas em eventos."""
from datetime import date, datetime, timezone
from dataclasses import replace
from typing import Any, Dict, Iterable, List
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from database.models import Company, Contact, EventOpportunityRow, Lead
from services.prospecting.default_profiles import get_default_registry
from services.prospecting.lead_opportunity_service import LeadOpportunityService
from services.prospecting.offer_matcher import OfferMatcher


def _event_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def parse_event_datetime(value: Any) -> datetime | None:
    """Converte timestamps de providers para datetimes UTC conscientes."""
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class EventOpportunityService:
    """Upsert e leitura org-scoped da saída do EventDiscoveryExecutor."""

    def replace_events(
        self,
        db: Session,
        organization_id: UUID,
        events: Iterable[Dict[str, Any]],
        offer_key: str | None = "trophies",
        resolve_leads: bool = True,
    ) -> List[EventOpportunityRow]:
        rows: List[EventOpportunityRow] = []
        for event in events:
            event_date = _event_date(event.get("event_date"))
            source_url = (event.get("source_url") or "").strip()
            name = (event.get("name") or "").strip()
            if not event_date or not source_url or not name:
                continue
            provider = (event.get("provider") or "unknown").strip()
            source_identifier = self._source_identifier(event)
            identity_filter = EventOpportunityRow.source_url == source_url
            if source_identifier:
                identity_filter = or_(
                    identity_filter,
                    (
                        EventOpportunityRow.provider == provider
                    ) & (
                        EventOpportunityRow.source_identifier == source_identifier
                    ),
                )
            row = db.scalars(select(EventOpportunityRow).where(
                EventOpportunityRow.organization_id == organization_id,
                identity_filter,
            )).first()
            if row is None:
                row = EventOpportunityRow(
                    organization_id=organization_id,
                    source_url=source_url,
                    name=name,
                    event_type=event.get("event_type") or "other",
                    event_date=event_date,
                )
                db.add(row)
            organizer_resolved = event.get("organizer_resolved") or {}
            lead = self._resolve_or_create_lead(
                db,
                organization_id,
                event,
                organizer_resolved,
            ) if resolve_leads else None
            row.offer_key = offer_key
            row.name = name
            row.event_type = event.get("event_type") or "other"
            row.event_date = event_date
            row.location = event.get("location")
            row.organizer = event.get("organizer")
            row.source_identifier = source_identifier
            row.provider = provider
            row.provider_status = event.get("provider_status") or "ok"
            row.status = self._status_for_event(event_date, row.expires_at)
            row.organizer_resolved = organizer_resolved
            row.lead_id = lead.id if lead else row.lead_id
            row.provenance = {
                "provider": provider,
                "source_url": source_url,
                "source_identifier": source_identifier,
                "organizer_resolution": organizer_resolved,
                "lead_resolution": "matched_or_created" if lead else "unresolved",
            }
            row.timing = event.get("timing") or {}
            row.confidence = float(event.get("confidence", 0.5))
            row.registration_status = event.get("registration_status") or "unknown"
            row.observed_at = self._datetime(event.get("observed_at"))
            row.expires_at = self._datetime(event.get("expires_at"))
            row.status = self._status_for_event(event_date, row.expires_at)
            row.updated_at = datetime.now(timezone.utc)
            rows.append(row)
        return rows

    def match_event_opportunities(
        self,
        db: Session,
        events: Iterable[EventOpportunityRow],
    ) -> Dict[str, Any]:
        """Conecta eventos futuros a oportunidades de troféus persistidas.

        O evento fornece sinais temporais e de intenção; o ``OfferMatcher``
        continua sendo a única regra de aderência à oferta. A operação é
        idempotente por lead/oferta e não envia mensagens automaticamente.

        Returns:
            Contadores de eventos casados, ignorados e falhos, além dos erros
            individuais para observabilidade do job.
        """
        matcher = OfferMatcher(get_default_registry())
        opportunity_service = LeadOpportunityService()
        result: Dict[str, Any] = {"matched": 0, "skipped": 0, "failed": 0, "errors": []}
        for event in events:
            if event.status != "upcoming" or not event.lead_id:
                result["skipped"] += 1
                continue
            lead = db.get(Lead, event.lead_id)
            if lead is None or lead.organization_id != event.organization_id:
                result["skipped"] += 1
                continue
            try:
                lead_data = {
                    "company_name": lead.company_name or lead.name,
                    "segment": lead.category,
                    "cnae": getattr(lead, "cnae", None),
                    "company_size": getattr(lead, "company_size", None),
                    "has_phone": bool(lead.phone),
                    "has_instagram": bool(getattr(lead, "instagram_url", None)),
                    # O vínculo de um evento futuro é evidência suficiente de
                    # que o organizador hospeda eventos, sem afirmar volume.
                    "hosts_events": True,
                }
                matches = matcher.match(lead_data, min_score=1)
                trophies = next((item for item in matches if item.offer_key == "trophies"), None)
                if trophies is None:
                    result["skipped"] += 1
                    continue
                evidence = list(dict.fromkeys([
                    *trophies.evidence,
                    "EVENT_SCHEDULED",
                    "ORGANIZER_RESOLVED" if event.organizer_resolved else "ORGANIZER_UNRESOLVED",
                ]))
                if (event.timing or {}).get("timing_score", 0) >= 60:
                    evidence.append("CONTACT_WINDOW_GOOD")
                enriched = replace(
                    trophies,
                    evidence=list(dict.fromkeys(evidence)),
                    signals_matched=list(dict.fromkeys([
                        *trophies.signals_matched, "EVENT_SCHEDULED",
                    ])),
                )
                opportunity_service.persist_opportunities(db, lead, [enriched])
                result["matched"] += 1
            except (TypeError, ValueError, AttributeError) as exc:
                result["failed"] += 1
                result["errors"].append({
                    "event_id": str(event.id),
                    "error_code": type(exc).__name__,
                })
        return result

    def prepare_event_actions(
        self,
        db: Session,
        events: Iterable[EventOpportunityRow],
    ) -> Dict[str, Any]:
        """Resolve contato já persistido e prepara próxima ação humana."""
        result: Dict[str, Any] = {"ready": 0, "needs_review": 0, "not_found": 0, "errors": []}
        channels = (get_default_registry().get("trophies").channels or {}).get("priority", [])
        for event in events:
            if event.status != "upcoming" or not event.lead_id:
                result["not_found"] += 1
                continue
            try:
                contacts = list(db.scalars(select(Contact).where(
                    Contact.lead_id == event.lead_id,
                ).order_by(Contact.is_primary.desc(), Contact.confidence.desc())).all())
                contact = next((item for item in contacts if item.email_verified and item.email), None)
                contact = contact or next((item for item in contacts if item.phone), None)
                contact = contact or next((item for item in contacts if item.email), None)
                if contact is None:
                    event.decision_maker_id = None
                    event.decision_maker_status = "not_found"
                    event.action_status = "needs_review"
                    event.next_action = "Encontrar e validar um decisor; não enviar mensagem automaticamente."
                    result["not_found"] += 1
                    continue
                channel = "email" if contact.email_verified and contact.email else "phone" if contact.phone else "email"
                if channel not in channels:
                    channel = next((item for item in channels if item in ("email", "phone", "whatsapp", "instagram")), channel)
                event.decision_maker_id = contact.id
                event.decision_maker_status = "resolved"
                event.recommended_channel = channel
                event.action_status = "ready" if contact.email_verified or contact.phone else "needs_review"
                event.next_action = (
                    f"Revisar {contact.name} e preparar contato por {channel}; não enviar mensagem automaticamente."
                )
                result[event.action_status] += 1
            except (TypeError, ValueError, AttributeError) as exc:
                event.action_status = "needs_review"
                event.decision_maker_status = "failed"
                result["needs_review"] += 1
                result["errors"].append({"event_id": str(event.id), "error_code": type(exc).__name__})
        return result

    @staticmethod
    def _source_identifier(event: Dict[str, Any]) -> str | None:
        """Retorna o identificador estável informado pela fonte, quando houver."""
        for key in ("source_identifier", "event_id", "external_id", "id"):
            value = event.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()[:255]
        return None

    @staticmethod
    def _resolve_or_create_lead(
        db: Session,
        organization_id: UUID,
        event: Dict[str, Any],
        resolved: Dict[str, Any],
    ) -> Lead | None:
        """Vincula o evento a um lead sem inferir uma empresa desconhecida.

        Match por nome é case-insensitive e org-scoped. Para uma resolução
        confiável (nome oficial + confidence >= 0.8), cria um Lead NOVO uma
        única vez; sem evidência suficiente, mantém o evento explicitamente
        sem lead.
        """
        official_name = str(resolved.get("official_name") or "").strip()
        organizer_name = str(event.get("organizer") or "").strip()
        candidate = official_name or organizer_name
        if not candidate:
            return None
        normalized = func.lower(func.trim(Lead.company_name)) == candidate.lower()
        lead = db.scalars(select(Lead).where(
            Lead.organization_id == organization_id,
            normalized,
        )).first()
        if lead:
            return lead
        confidence = float(resolved.get("confidence") or 0)
        if not official_name or confidence < 0.8:
            return None
        location = str(event.get("location") or "Não informado").strip()
        city = location.split(",", 1)[0].strip()[:100] or "Não informado"
        company = db.scalars(select(Company).where(
            Company.organization_id == organization_id,
            func.lower(func.trim(Company.company_name)) == official_name.lower(),
        )).first()
        if company is None:
            company = Company(
                organization_id=organization_id,
                company_name=official_name,
                name=official_name,
                category="organizer",
                city=city,
            )
            db.add(company)
            db.flush()
        lead = Lead(
            organization_id=organization_id,
            company_id=company.id,
            name=official_name,
            company_name=official_name,
            city=city,
            category="organizer",
            notes="Lead criado a partir de Event Discovery; revisar dados antes do contato.",
        )
        db.add(lead)
        db.flush()
        return lead

    @staticmethod
    def _datetime(value: Any) -> datetime | None:
        return parse_event_datetime(value)

    @staticmethod
    def _status_for_event(event_date: date, expires_at: datetime | None) -> str:
        if expires_at and expires_at <= datetime.now(timezone.utc):
            return "expired"
        return "expired" if event_date < datetime.now(timezone.utc).date() else "upcoming"

    def list_for_organization(self, db: Session, organization_id: UUID) -> List[EventOpportunityRow]:
        return list(db.scalars(select(EventOpportunityRow).where(
            EventOpportunityRow.organization_id == organization_id,
        ).order_by(EventOpportunityRow.event_date.asc())).all())

    def expire_events(
        self,
        db: Session,
        organization_id: UUID | None = None,
        now: datetime | None = None,
    ) -> int:
        """Marca eventos vencidos uma única vez e retorna as transições feitas."""
        now = now or datetime.now(timezone.utc)
        query = select(EventOpportunityRow).where(
            EventOpportunityRow.status == "upcoming",
            or_(
                EventOpportunityRow.event_date < now.date(),
                EventOpportunityRow.expires_at <= now,
            ),
        )
        if organization_id:
            query = query.where(EventOpportunityRow.organization_id == organization_id)
        rows = list(db.scalars(query).all())
        changed = 0
        for row in rows:
            row.status = "expired"
            row.updated_at = now
            changed += 1
        return changed