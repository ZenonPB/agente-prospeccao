"""Endpoints org-scoped para eventos descobertos e métricas comerciais."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.auth.dependencies import get_user_organization, require_analyst
from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/events")
def list_events(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(require_analyst()),
):
    """Lista eventos futuros persistidos pelo Event Discovery."""
    from src.db.models import EventOpportunityRow

    rows = db.query(EventOpportunityRow).filter(
        EventOpportunityRow.organization_id == org.id,
        EventOpportunityRow.event_date >= date.today(),
    ).order_by(EventOpportunityRow.event_date.asc()).limit(limit).all()
    return {
        "events": [
            {
                "id": str(row.id),
                "name": row.name,
                "event_type": row.event_type,
                "event_date": row.event_date.isoformat(),
                "location": row.location,
                "source_url": row.source_url,
                "organizer": row.organizer,
                "organizer_resolved": row.organizer_resolved or {},
                "timing": row.timing or {},
                "offer_key": row.offer_key,
                "registration_status": row.registration_status,
            }
            for row in rows
        ],
        "total": len(rows),
    }


@router.get("/outcomes")
def list_outcomes(
    offer_key: Optional[str] = Query(None, max_length=64),
    offer_version: Optional[str] = Query(None, max_length=32),
    db: Session = Depends(get_db),
    org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(require_analyst()),
):
    """Retorna outcomes e conversão por oferta/versão, sem dados de outra org."""
    from src.db.models import CommercialOutcomeRow
    from services.prospecting.commercial_outcome_service import CommercialOutcomeService

    rows = CommercialOutcomeService().list_for_organization(
        db, org.id, offer_key=offer_key, offer_version=offer_version,
    )
    return CommercialOutcomeService().metrics(rows) | {
        "outcomes": [
            {
                "id": str(row.id),
                "lead_id": str(row.lead_id),
                "offer_key": row.offer_key,
                "offer_version": row.offer_version,
                "outcome": row.outcome,
                "value": float(row.value or 0),
                "provider": row.provider,
                "recorded_at": row.recorded_at.isoformat() if row.recorded_at else None,
            }
            for row in rows
        ],
    }