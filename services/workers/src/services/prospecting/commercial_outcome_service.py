"""Persistência de outcomes comerciais para aprendizagem auditável."""
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import CommercialOutcomeRow, Lead, LeadOpportunityRow


class CommercialOutcomeService:
    """Registra resultados reais sem duplicar eventos comerciais."""

    def record_for_lead(
        self,
        db: Session,
        organization_id: UUID,
        lead_id: UUID,
        outcome: str,
        event_key: str,
        value: float = 0.0,
        offer_key: str | None = None,
        offer_version: str | None = None,
        provider: str | None = None,
        outreach_at: datetime | None = None,
    ) -> CommercialOutcomeRow:
        lead = db.scalars(select(Lead).where(
            Lead.id == lead_id,
            Lead.organization_id == organization_id,
        )).first()
        if lead is None:
            raise ValueError("Lead não pertence à organização informada")

        existing = db.scalars(select(CommercialOutcomeRow).where(
            CommercialOutcomeRow.organization_id == organization_id,
            CommercialOutcomeRow.event_key == event_key,
        )).first()
        if existing:
            return existing

        if not offer_key:
            opportunity = db.scalars(select(LeadOpportunityRow).where(
                LeadOpportunityRow.organization_id == organization_id,
                LeadOpportunityRow.lead_id == lead_id,
            ).order_by(LeadOpportunityRow.score.desc())).first()
            offer_key = opportunity.offer_key if opportunity else "unknown"
            offer_version = offer_version or (opportunity.offer_version if opportunity else None)

        row = CommercialOutcomeRow(
            organization_id=organization_id,
            lead_id=lead_id,
            offer_key=offer_key,
            offer_version=offer_version,
            outcome=outcome,
            value=value or 0,
            provider=provider,
            outreach_at=outreach_at,
            event_key=event_key,
            recorded_at=datetime.now(timezone.utc),
        )
        db.add(row)
        return row

    def list_for_organization(
        self,
        db: Session,
        organization_id: UUID,
        offer_key: str | None = None,
        offer_version: str | None = None,
    ) -> List[CommercialOutcomeRow]:
        query = select(CommercialOutcomeRow).where(
            CommercialOutcomeRow.organization_id == organization_id,
        )
        if offer_key:
            query = query.where(CommercialOutcomeRow.offer_key == offer_key)
        if offer_version:
            query = query.where(CommercialOutcomeRow.offer_version == offer_version)
        return list(db.scalars(query.order_by(CommercialOutcomeRow.recorded_at.desc())).all())

    def metrics(self, rows: Iterable[CommercialOutcomeRow]) -> Dict[str, Any]:
        materialized = list(rows)
        groups: Dict[tuple[str, str | None], List[CommercialOutcomeRow]] = {}
        for row in materialized:
            groups.setdefault((row.offer_key, row.offer_version), []).append(row)
        result = []
        for (offer_key, version), items in groups.items():
            wins = sum(1 for item in items if item.outcome == "WON")
            result.append({
                "offer_key": offer_key,
                "offer_version": version,
                "total": len(items),
                "won": wins,
                "conversion_rate": round(wins / len(items) * 100, 2) if items else 0.0,
                "average_ticket": round(sum(float(item.value or 0) for item in items if item.outcome == "WON") / wins, 2) if wins else 0.0,
            })
        return {"metrics": result, "total_outcomes": len(materialized)}