from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from src.db.dependencies import get_db
from src.db.models import Lead, LeadStatus, Enrichment
from src.auth.dependencies import get_current_user
from src.db.models import User

router = APIRouter(prefix="/leads", tags=["leads"])


class UpdateLeadStatusRequest(BaseModel):
    status: LeadStatus


@router.get("")
def list_leads(
    status: Optional[str] = None,
    campaign_id: Optional[str] = None,
    search: Optional[str] = None,
    min_score: Optional[int] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = db.query(Lead)

    if status:
        status_list = [s.strip() for s in status.split(",") if s.strip()]
        try:
            enum_values = [LeadStatus(s) for s in status_list]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Status inválido: {status_list}")
        if len(enum_values) == 1:
            query = query.filter(Lead.status == enum_values[0])
        else:
            query = query.filter(Lead.status.in_(enum_values))
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
def lead_stats(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    total = db.query(Lead).count()
    qualified = db.query(Lead).filter(Lead.status == LeadStatus.QUALIFICADO).count()
    contacted = db.query(Lead).filter(Lead.status == LeadStatus.CONTATADO).count()
    meetings = db.query(Lead).filter(Lead.status == LeadStatus.REUNIAO_MARCADA).count()
    avg_score = db.query(func.avg(Lead.qualification_score)).scalar() or 0

    by_status = {}
    for s in LeadStatus:
        count = db.query(Lead).filter(Lead.status == s).count()
        if count > 0:
            by_status[s.value] = count

    return {
        "total": total,
        "by_status": by_status,
        "avg_score": round(float(avg_score), 1),
        "qualified_count": qualified,
        "qualified_pct": round((qualified / total * 100), 1) if total > 0 else 0,
        "contacted_count": contacted,
        "meetings_count": meetings,
    }


@router.patch("/{lead_id}/status")
def update_lead_status(
    lead_id: str,
    body: UpdateLeadStatusRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    lead.status = body.status
    db.commit()
    db.refresh(lead)

    return {
        "id": str(lead.id),
        "company_name": lead.company_name,
        "status": lead.status.value if lead.status else None,
    }


@router.get("/{lead_id}")
def get_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    enrichment = db.query(Enrichment).filter(Enrichment.lead_id == lead.id).first()

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
        "enrichment": {
            "id": str(enrichment.id),
            "lead_id": str(enrichment.lead_id),
            "website_exists": enrichment.website_exists,
            "ssl_ok": enrichment.ssl_ok,
            "https_redirect_ok": enrichment.https_redirect_ok,
            "responsive_design": enrichment.responsive_design,
            "cms": enrichment.cms,
            "lighthouse_score": enrichment.lighthouse_score,
            "seo_errors": enrichment.seo_errors,
            "load_time_ms": enrichment.load_time_ms,
            "security_issues": enrichment.security_issues,
            "raw_technical_data": enrichment.raw_technical_data,
            "created_at": enrichment.created_at.isoformat() if enrichment.created_at else None,
            "updated_at": enrichment.updated_at.isoformat() if enrichment.updated_at else None,
        } if enrichment else None,
    }
