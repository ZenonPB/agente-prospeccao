"""Persistência das oportunidades descobertas em eventos."""
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import EventOpportunityRow


def _event_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


class EventOpportunityService:
    """Upsert e leitura org-scoped da saída do EventDiscoveryExecutor."""

    def replace_events(
        self,
        db: Session,
        organization_id: UUID,
        events: Iterable[Dict[str, Any]],
        offer_key: str | None = "trophies",
    ) -> List[EventOpportunityRow]:
        rows: List[EventOpportunityRow] = []
        for event in events:
            event_date = _event_date(event.get("event_date"))
            source_url = (event.get("source_url") or "").strip()
            name = (event.get("name") or "").strip()
            if not event_date or not source_url or not name:
                continue
            row = db.scalars(select(EventOpportunityRow).where(
                EventOpportunityRow.organization_id == organization_id,
                EventOpportunityRow.source_url == source_url,
            )).first()
            if row is None:
                row = EventOpportunityRow(
                    organization_id=organization_id,
                    source_url=source_url,
                )
                db.add(row)
            row.offer_key = offer_key
            row.name = name
            row.event_type = event.get("event_type") or "other"
            row.event_date = event_date
            row.location = event.get("location")
            row.organizer = event.get("organizer")
            row.organizer_resolved = event.get("organizer_resolved") or {}
            row.timing = event.get("timing") or {}
            row.confidence = float(event.get("confidence", 0.5))
            row.registration_status = event.get("registration_status") or "unknown"
            row.observed_at = self._datetime(event.get("observed_at"))
            row.expires_at = self._datetime(event.get("expires_at"))
            row.updated_at = datetime.now(timezone.utc)
            rows.append(row)
        return rows

    @staticmethod
    def _datetime(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    def list_for_organization(self, db: Session, organization_id: UUID) -> List[EventOpportunityRow]:
        return list(db.scalars(select(EventOpportunityRow).where(
            EventOpportunityRow.organization_id == organization_id,
        ).order_by(EventOpportunityRow.event_date.asc())).all())