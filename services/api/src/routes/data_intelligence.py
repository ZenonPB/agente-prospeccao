from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, get_user_organization, require_analyst
from src.db.dependencies import get_db
from src.db.models import Job, JobStatus, JobType, Lead, Organization, OrganizationMember, User
from src.services.data_health_service import DataHealthService
from src.services.data_intelligence_service import DataIntelligenceService


router = APIRouter(prefix="/data-intelligence", tags=["data-intelligence"])


class RefreshPlanRequest(BaseModel):
    limit: int = Field(25, ge=1, le=100)
    enqueue: bool = False


@router.get("/health")
def get_data_health(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    return DataHealthService(db, org.id).overview(limit=limit)


@router.get("/leads/{lead_id}")
def get_lead_intelligence(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == org.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    return DataIntelligenceService(db, org.id).analyze_lead(lead, persist=False)


@router.post("/leads/{lead_id}/recompute")
def recompute_lead_intelligence(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == org.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    return DataIntelligenceService(db, org.id).analyze_lead(lead, persist=True)


@router.post("/refresh-plan")
def create_refresh_plan(
    request: RefreshPlanRequest,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    """Prioriza refresh e, opcionalmente, agenda reanálise por campanha.

    Não dispara provider diretamente no request. Quando `enqueue=true`, cria
    jobs LEAD_ENRICHMENT existentes, um por campanha, preservando a fila e a
    observabilidade já usadas pelo pipeline.
    """
    candidates = DataHealthService(db, org.id).refresh_candidates(limit=request.limit)
    if not request.enqueue:
        return {"candidates": candidates, "jobs": []}

    lead_ids = [item["lead_id"] for item in candidates]
    if not lead_ids:
        return {"candidates": [], "jobs": []}

    leads = db.query(Lead).filter(Lead.organization_id == org.id, Lead.id.in_(lead_ids)).all()
    by_campaign: dict[object, list[Lead]] = {}
    for lead in leads:
        if lead.campaign_id:
            by_campaign.setdefault(lead.campaign_id, []).append(lead)

    jobs: list[dict[str, str]] = []
    for campaign_id, campaign_leads in by_campaign.items():
        campaign_id_str = str(campaign_id)
        # Evita duplicar refresh pendente para a mesma campanha.
        pending = db.query(Job).filter(
            Job.organization_id == org.id,
            Job.campaign_id == campaign_id,
            Job.job_type == JobType.LEAD_ENRICHMENT,
            Job.status.in_([JobStatus.PENDING, JobStatus.IN_PROGRESS]),
        ).first()
        if pending:
            jobs.append({"job_id": str(pending.id), "campaign_id": campaign_id_str, "status": "already_pending"})
            continue
        job = Job(
            job_type=JobType.LEAD_ENRICHMENT,
            status=JobStatus.PENDING,
            organization_id=org.id,
            campaign_id=campaign_id,
            payload={
                "campaign_id": campaign_id_str,
                "reanalyze_only": True,
                "unscored_only": False,
                "max_leads": min(len(campaign_leads), 200),
                "refresh_reason": "stale_data",
                "refresh_lead_ids": [str(item.id) for item in campaign_leads],
            },
        )
        db.add(job)
        db.flush()
        jobs.append({"job_id": str(job.id), "campaign_id": campaign_id_str, "status": "queued"})

    db.commit()
    return {"candidates": candidates, "jobs": jobs}
