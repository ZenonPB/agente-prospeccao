from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from src.db.dependencies import get_db
from src.db.models import Lead, LeadStatus

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("")
def list_leads(
    status: Optional[str] = None,
    campaign_id: Optional[str] = None,
    search: Optional[str] = None,
    min_score: Optional[int] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(Lead)

    if status:
        query = query.filter(Lead.status == status)
    if campaign_id:
        query = query.filter(Lead.campaign_id == campaign_id)
    if search:
        query = query.filter(Lead.company_name.ilike(f"%{search}%"))
    if min_score is not None:
        query = query.filter(Lead.qualification_score >= min_score)

    total = query.count()
    leads = query.order_by(Lead.qualification_score.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "leads": [
            {
                "id": str(lead.id),
                "company_name": lead.company_name,
                "website": lead.website,
                "phone": lead.phone,
                "email": lead.email,
                "category": lead.category,
                "city": lead.city,
                "state": lead.state,
                "country": lead.country,
                "status": lead.status.value if lead.status else None,
                "qualification_score": lead.qualification_score,
                "qualification_reason": lead.qualification_reason,
                "primary_need": lead.primary_need,
                "campaign_id": str(lead.campaign_id) if lead.campaign_id else None,
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
                "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
            }
            for lead in leads
        ],
    }


@router.get("/stats")
def lead_stats(db: Session = Depends(get_db)):
    total = db.query(Lead).count()
    qualified = db.query(Lead).filter(Lead.status == LeadStatus.QUALIFICADO).count()
    contacted = db.query(Lead).filter(Lead.status == LeadStatus.CONTATADO).count()
    meetings = db.query(Lead).filter(Lead.status == LeadStatus.REUNIAO_MARCADA).count()
    avg_score = db.query(func.avg(Lead.qualification_score)).scalar() or 0

    return {
        "total": total,
        "qualified": qualified,
        "contacted": contacted,
        "meetings": meetings,
        "avg_score": round(float(avg_score), 1),
    }


@router.get("/{lead_id}")
def get_lead(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return {"error": "Lead not found"}, 404

    return {
        "id": str(lead.id),
        "company_name": lead.company_name,
        "website": lead.website,
        "phone": lead.phone,
        "email": lead.email,
        "category": lead.category,
        "city": lead.city,
        "state": lead.state,
        "country": lead.country,
        "status": lead.status.value if lead.status else None,
        "qualification_score": lead.qualification_score,
        "qualification_reason": lead.qualification_reason,
        "primary_need": lead.primary_need,
        "campaign_id": str(lead.campaign_id) if lead.campaign_id else None,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }
