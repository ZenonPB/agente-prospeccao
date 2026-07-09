from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from src.db.dependencies import get_db
from src.db.models import Campaign, CampaignStatus, Lead

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("")
def list_campaigns(
    status: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
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
            from sqlalchemy import func
            avg_score = db.query(func.avg(Lead.qualification_score)).filter(Lead.campaign_id == campaign.id).scalar() or 0

        result.append({
            "id": str(campaign.id),
            "name": campaign.name,
            "target_service": campaign.target_service,
            "target_segment": campaign.target_segment,
            "target_city": campaign.target_city,
            "target_state": campaign.target_state,
            "target_country": campaign.target_country,
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


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        return {"error": "Campaign not found"}, 404

    lead_count = db.query(Lead).filter(Lead.campaign_id == campaign.id).count()
    from sqlalchemy import func
    avg_score = db.query(func.avg(Lead.qualification_score)).filter(Lead.campaign_id == campaign.id).scalar() or 0

    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "target_service": campaign.target_service,
        "target_segment": campaign.target_segment,
        "target_city": campaign.target_city,
        "target_state": campaign.target_state,
        "target_country": campaign.target_country,
        "status": campaign.status.value if campaign.status else None,
        "lead_count": lead_count,
        "avg_score": round(float(avg_score), 1),
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
    }
