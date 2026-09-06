"""Endpoints org-scoped para eventos descobertos e métricas comerciais."""
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.dependencies import get_user_organization, require_analyst
from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember, User, CommercialComparison
from src.auth.dependencies import get_current_user, require_manager

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


class ComparisonApprovalRequest(BaseModel):
    approved_version: str = Field(..., min_length=1, max_length=32)
    evidence: str = Field(..., min_length=3, max_length=1000)


@router.get("/events")
def list_events(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(require_analyst()),
):
    """Lista eventos ainda acionáveis; históricos permanecem consultáveis."""
    from src.db.models import EventOpportunityRow

    rows = db.query(EventOpportunityRow).filter(
        EventOpportunityRow.organization_id == org.id,
        EventOpportunityRow.status == "upcoming",
        EventOpportunityRow.event_date >= date.today(),
        (EventOpportunityRow.expires_at.is_(None) | EventOpportunityRow.expires_at > datetime.now(timezone.utc)),
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
                "status": row.status,
                "provider": row.provider,
                "provider_status": row.provider_status,
                "source_identifier": row.source_identifier,
                "provenance": row.provenance or {},
                "lead_id": str(row.lead_id) if row.lead_id else None,
            }
            for row in rows
        ],
        "total": len(rows),
    }


@router.get("/comparisons")
def compare_versions(
    offer_key: str = Query(..., min_length=1, max_length=64),
    version_a: str = Query(..., min_length=1, max_length=32),
    version_b: str = Query(..., min_length=1, max_length=32),
    min_samples: int = Query(5, ge=1, le=10000),
    db: Session = Depends(get_db),
    org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(require_analyst()),
):
    from src.services.commercial_comparison_service import CommercialComparisonService
    comparison = CommercialComparisonService().compute_and_persist(
        db, org.id, offer_key, version_a, version_b, min_samples,
    )
    db.commit()
    return _comparison_dict(comparison)


@router.post("/comparisons/{comparison_id}/approval")
def approve_comparison(
    comparison_id: str,
    body: ComparisonApprovalRequest,
    db: Session = Depends(get_db),
    org: Organization = Depends(get_user_organization),
    actor: User = Depends(get_current_user),
    _member: OrganizationMember = Depends(require_manager()),
):
    from uuid import UUID
    from src.services.commercial_comparison_service import CommercialComparisonService
    try:
        comparison = CommercialComparisonService().approve(
            db, org.id, UUID(comparison_id), body.approved_version, actor, body.evidence,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return _comparison_dict(comparison)


def _comparison_dict(comparison: CommercialComparison) -> dict:
    return {
        "id": str(comparison.id),
        "offer_key": comparison.offer_key,
        "version_a": comparison.version_a,
        "version_b": comparison.version_b,
        "result": comparison.result,
        "computed_at": comparison.computed_at.isoformat() if comparison.computed_at else None,
        "approved_version": comparison.approved_version,
        "approved_by_id": str(comparison.approved_by_id) if comparison.approved_by_id else None,
        "approved_at": comparison.approved_at.isoformat() if comparison.approved_at else None,
        "approval_evidence": comparison.approval_evidence,
    }


@router.get("/outcomes")
def list_outcomes(
    offer_key: Optional[str] = Query(None, max_length=64),
    offer_version: Optional[str] = Query(None, max_length=32),
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(require_analyst()),
):
    """Retorna outcomes e conversão por oferta/versão, sem dados de outra org."""
    from src.db.models import CommercialOutcomeRow
    from services.prospecting.commercial_outcome_service import CommercialOutcomeService

    rows = CommercialOutcomeService().list_for_organization(
        db,
        org.id,
        offer_key=offer_key,
        offer_version=offer_version,
        date_from=date_from,
        date_to=date_to,
    )
    return CommercialOutcomeService().metrics(rows) | {
        "outcomes": [
            {
                "id": str(row.id),
                "lead_id": str(row.lead_id),
                "lead_opportunity_id": str(row.lead_opportunity_id) if row.lead_opportunity_id else None,
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