from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, get_user_organization, require_analyst, require_manager
from src.db.dependencies import get_db
from src.db.models import Job, JobStatus, JobType, Lead, Organization, OrganizationMember, User
from src.services.continuous_intelligence_service import ContinuousIntelligenceService
from src.services.data_health_service import DataHealthService
from src.services.data_intelligence_service import DataIntelligenceService
from src.services.prospecting_automation_service import (
    AGENT_STATES,
    AgentStateService,
    AlertService,
    SavedSearchService,
    serialize_alert,
    serialize_saved_search,
)
from database.phase56_models import CaseStudy, EventSeries, ProspectingAgentState, SavedProspectingSearch
from services.prospecting.offer_excellence_service import CaseStudyMatcher, EventSeriesService


router = APIRouter(prefix="/data-intelligence", tags=["data-intelligence"])


class RefreshPlanRequest(BaseModel):
    limit: int = Field(25, ge=1, le=100)
    enqueue: bool = False


class SavedSearchCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    offer_key: Optional[str] = Field(None, max_length=64)
    filters: dict[str, Any] = Field(default_factory=dict)
    schedule: str = Field("manual", max_length=64)
    notification_policy: dict[str, Any] = Field(default_factory=dict)


class SavedSearchPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=160)
    offer_key: Optional[str] = Field(None, max_length=64)
    filters: Optional[dict[str, Any]] = None
    schedule: Optional[str] = Field(None, max_length=64)
    notification_policy: Optional[dict[str, Any]] = None
    enabled: Optional[bool] = None


class AlertStatusPatch(BaseModel):
    status: Literal["new", "read", "dismissed", "actioned"]


class CaseStudyCreate(BaseModel):
    offer_key: str = Field(..., min_length=2, max_length=64)
    title: str = Field(..., min_length=2, max_length=180)
    segments: list[str] = Field(default_factory=list, max_length=30)
    problem: str = Field(..., min_length=4, max_length=5000)
    solution: str = Field(..., min_length=4, max_length=5000)
    proof: Optional[str] = Field(None, max_length=5000)
    assets: Optional[dict[str, Any]] = None


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


@router.post("/watch/run-once")
async def run_watch_once(
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    return await ContinuousIntelligenceService(db).run_once_for_org(org, force=True)


@router.get("/saved-searches")
def list_saved_searches(
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    return {"items": SavedSearchService(db, org.id).list()}


@router.post("/saved-searches", status_code=status.HTTP_201_CREATED)
def create_saved_search(
    body: SavedSearchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    row = SavedSearchService(db, org.id).create(
        owner_user_id=user.id,
        name=body.name,
        offer_key=body.offer_key,
        filters=body.filters,
        schedule=body.schedule,
        notification_policy=body.notification_policy,
    )
    return serialize_saved_search(row)


@router.patch("/saved-searches/{search_id}")
def patch_saved_search(
    search_id: str,
    body: SavedSearchPatch,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    row = SavedSearchService(db, org.id).update(search_id, **body.model_dump(exclude_unset=True))
    if row is None:
        raise HTTPException(status_code=404, detail="Busca salva não encontrada")
    return serialize_saved_search(row)


@router.delete("/saved-searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_search(
    search_id: str,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    if not SavedSearchService(db, org.id).delete(search_id):
        raise HTTPException(status_code=404, detail="Busca salva não encontrada")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/saved-searches/{search_id}/run")
def run_saved_search(
    search_id: str,
    limit: int = Query(100, ge=1, le=250),
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    service = SavedSearchService(db, org.id)
    row = db.query(SavedProspectingSearch).filter(
        SavedProspectingSearch.id == search_id,
        SavedProspectingSearch.organization_id == org.id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Busca salva não encontrada")
    return service.run(row, limit=limit)


@router.get("/alerts")
def list_alerts(
    alert_status: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    if alert_status and alert_status not in {"new", "read", "dismissed", "actioned"}:
        raise HTTPException(status_code=400, detail="status de alerta inválido")
    return {"items": AlertService(db, org.id).list(status=alert_status, limit=limit)}


@router.patch("/alerts/{alert_id}")
def patch_alert(
    alert_id: str,
    body: AlertStatusPatch,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    row = AlertService(db, org.id).set_status(alert_id, body.status)
    if row is None:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    return serialize_alert(row)


@router.post("/event-series/refresh")
def refresh_event_series(
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    rows = EventSeriesService.rebuild(db, org.id)
    created_alerts = AlertService(db, org.id).materialize_rebuy_alerts()
    db.commit()
    return {"series": len(rows), "rebuy_alerts_created": created_alerts}


@router.get("/event-series")
def list_event_series(
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    rows = db.query(EventSeries).filter(EventSeries.organization_id == org.id).order_by(EventSeries.updated_at.desc()).all()
    return {
        "items": [
            {
                "id": str(row.id),
                "series_key": row.series_key,
                "name": row.name,
                "family": row.family,
                "recurrence_confidence": float(row.recurrence_confidence or 0),
                "expected_next_window": row.expected_next_window,
                "latest_event_id": str(row.latest_event_id) if row.latest_event_id else None,
                "metadata": row.series_metadata,
            }
            for row in rows
        ]
    }


@router.get("/case-studies")
def list_case_studies(
    offer_key: Optional[str] = None,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    query = db.query(CaseStudy).filter(
        CaseStudy.active.is_(True),
        (CaseStudy.organization_id == org.id) | (CaseStudy.organization_id.is_(None)),
    )
    if offer_key:
        query = query.filter(CaseStudy.offer_key == offer_key)
    rows = query.order_by(CaseStudy.offer_key.asc(), CaseStudy.title.asc()).all()
    return {
        "items": [
            {
                "id": str(row.id),
                "offer_key": row.offer_key,
                "title": row.title,
                "segments": row.segments or [],
                "problem": row.problem,
                "solution": row.solution,
                "proof": row.proof,
                "assets": row.assets,
                "scope": "workspace" if row.organization_id else "global",
            }
            for row in rows
        ]
    }


@router.post("/case-studies", status_code=status.HTTP_201_CREATED)
def create_case_study(
    body: CaseStudyCreate,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    row = CaseStudy(
        organization_id=org.id,
        offer_key=body.offer_key.strip(),
        title=body.title.strip(),
        segments=[segment.strip() for segment in body.segments if segment.strip()],
        problem=body.problem.strip(),
        solution=body.solution.strip(),
        proof=body.proof.strip() if body.proof else None,
        assets=body.assets,
        active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "offer_key": row.offer_key, "title": row.title}


@router.get("/leads/{lead_id}/case-study")
def match_case_study(
    lead_id: str,
    offer_key: str = Query(..., min_length=2, max_length=64),
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == org.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    match = CaseStudyMatcher.match(db, org.id, lead, offer_key)
    return {"match": match}


@router.post("/agent-states/refresh")
def refresh_agent_states(
    limit: int = Query(250, ge=1, le=1000),
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    return {"states": AgentStateService(db, org.id).refresh_all(limit=limit)}


@router.get("/agent-states")
def list_agent_states(
    agent_state: Optional[str] = Query(None, alias="state"),
    limit: int = Query(250, ge=1, le=1000),
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    if agent_state and agent_state not in AGENT_STATES:
        raise HTTPException(status_code=400, detail="estado do agente inválido")
    query = db.query(ProspectingAgentState).filter(ProspectingAgentState.organization_id == org.id)
    if agent_state:
        query = query.filter(ProspectingAgentState.state == agent_state)
    rows = query.order_by(ProspectingAgentState.changed_at.desc()).limit(limit).all()
    return {
        "items": [
            {
                "id": str(row.id),
                "lead_id": str(row.lead_id),
                "state": row.state,
                "reason": row.reason,
                "evidence": row.evidence,
                "changed_at": row.changed_at.isoformat() if row.changed_at else None,
            }
            for row in rows
        ]
    }


@router.post("/refresh-plan")
def create_refresh_plan(
    request: RefreshPlanRequest,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
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
