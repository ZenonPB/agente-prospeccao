from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from pydantic import BaseModel, Field
from src.db.dependencies import get_db
from src.db.models import Campaign, CampaignStatus, Lead, User
from src.auth.dependencies import get_current_user

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CreateCampaignRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    target_service: Optional[str] = None
    target_segment: Optional[str] = None
    target_city: Optional[str] = None
    target_state: Optional[str] = None
    target_country: Optional[str] = None
    analysis_profile: str = "web_presence"


@router.get("")
def list_campaigns(
    status: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Campaign)

    if status:
        query = query.filter(Campaign.status == status)

    total = query.count()
    campaigns = query.order_by(Campaign.created_at.desc()).offset(offset).limit(limit).all()

    result = []
    for campaign in campaigns:
        lead_count = db.query(Lead).filter(Lead.campaign_id == campaign.id).count()
        avg_score = 0
        if lead_count > 0:
            avg_score = db.query(func.avg(Lead.qualification_score)).filter(Lead.campaign_id == campaign.id).scalar() or 0

        result.append({
            "id": str(campaign.id),
            "name": campaign.name,
            "target_service": campaign.target_service,
            "target_segment": campaign.target_segment,
            "target_city": campaign.target_city,
            "target_state": campaign.target_state,
            "target_country": campaign.target_country,
            "analysis_profile": campaign.analysis_profile.value if campaign.analysis_profile else "web_presence",
            "status": campaign.status.value if campaign.status else None,
            "lead_count": lead_count,
            "avg_score": round(float(avg_score), 1),
            "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
            "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
        })

    return {
        "total": total,
        "campaigns": result,
    }


@router.post("", status_code=201)
def create_campaign(
    request: CreateCampaignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    campaign = Campaign(
        user_id=user.id,
        name=request.name,
        target_service=request.target_service,
        target_segment=request.target_segment,
        target_city=request.target_city,
        target_state=request.target_state,
        target_country=request.target_country or "Brasil",
        analysis_profile=request.analysis_profile,
        status=CampaignStatus.ACTIVE,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return {
        "id": str(campaign.id),
        "user_id": str(campaign.user_id),
        "name": campaign.name,
        "target_service": campaign.target_service,
        "target_segment": campaign.target_segment,
        "target_city": campaign.target_city,
        "target_state": campaign.target_state,
        "target_country": campaign.target_country,
        "analysis_profile": campaign.analysis_profile.value if campaign.analysis_profile else "web_presence",
        "status": campaign.status.value if campaign.status else None,
        "lead_count": 0,
        "avg_score": 0,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
    }


@router.get("/{campaign_id}")
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    lead_count = db.query(Lead).filter(Lead.campaign_id == campaign.id).count()
    avg_score = db.query(func.avg(Lead.qualification_score)).filter(Lead.campaign_id == campaign.id).scalar() or 0

    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "target_service": campaign.target_service,
        "target_segment": campaign.target_segment,
        "target_city": campaign.target_city,
        "target_state": campaign.target_state,
        "target_country": campaign.target_country,
        "analysis_profile": campaign.analysis_profile.value if campaign.analysis_profile else "web_presence",
        "status": campaign.status.value if campaign.status else None,
        "lead_count": lead_count,
        "avg_score": round(float(avg_score), 1),
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
    }
