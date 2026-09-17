"""Analytics comerciais explicáveis e org-scoped."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.auth.dependencies import get_user_organization, require_analyst
from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember
from src.services.commercial_intelligence_service import CommercialIntelligenceService
from src.services.pilot_outcome_metrics import summarize_campaign_outcomes

router = APIRouter(prefix="/commercial-intelligence", tags=["commercial-intelligence"])


def _service(
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
) -> CommercialIntelligenceService:
    return CommercialIntelligenceService(db, org.id)


@router.get("/dashboard")
def dashboard(service: CommercialIntelligenceService = Depends(_service)):
    return service.dashboard()


@router.get("/signals")
def signals(
    min_sample: int = Query(3, ge=1, le=1000),
    service: CommercialIntelligenceService = Depends(_service),
):
    return {"items": service.signal_effectiveness(min_sample=min_sample)}


@router.get("/providers")
def providers(service: CommercialIntelligenceService = Depends(_service)):
    return {"items": service.provider_effectiveness()}


@router.get("/precision")
def precision(service: CommercialIntelligenceService = Depends(_service)):
    return service.precision_at_k()


@router.get("/coverage")
def coverage(service: CommercialIntelligenceService = Depends(_service)):
    return service.coverage()


@router.get("/segments")
def segments(
    min_sample: int = Query(5, ge=1, le=1000),
    service: CommercialIntelligenceService = Depends(_service),
):
    return {"items": service.niche_priors(min_sample=min_sample)}


@router.get("/pilot-readiness")
def pilot_readiness(
    campaign_id: UUID | None = Query(None),
    service: CommercialIntelligenceService = Depends(_service),
):
    """Diagnóstico read-only; não promove shadow nem executa I/O externo."""
    result = service.pilot_readiness(campaign_id=campaign_id)
    result["outcomes"] = summarize_campaign_outcomes(
        service.db,
        service.organization_id,
        campaign_id=campaign_id,
    )
    return result
