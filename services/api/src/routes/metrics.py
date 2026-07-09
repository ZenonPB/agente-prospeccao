from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.db.dependencies import get_db
from src.db.models import Lead, Campaign, LeadStatus, CampaignStatus

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
def get_metrics(db: Session = Depends(get_db)):
    total_leads = db.query(Lead).count()
    qualified = db.query(Lead).filter(Lead.status == LeadStatus.QUALIFICADO).count()
    contacted = db.query(Lead).filter(Lead.status == LeadStatus.CONTATADO).count()
    meetings = db.query(Lead).filter(Lead.status == LeadStatus.REUNIAO_MARCADA).count()

    # Response rate: responded / contacted
    responded = db.query(Lead).filter(Lead.status == LeadStatus.RESPONDIDO).count()
    response_rate = (responded / contacted * 100) if contacted > 0 else 0

    # Funnel data
    funnel = []
    for status, label in [
        (LeadStatus.NOVO, "Novos"),
        (LeadStatus.ANALISADO, "Analisados"),
        (LeadStatus.QUALIFICADO, "Qualificados"),
        (LeadStatus.CONTATADO, "Contatados"),
        (LeadStatus.RESPONDIDO, "Responderam"),
        (LeadStatus.REUNIAO_MARCADA, "Reuniões"),
    ]:
        count = db.query(Lead).filter(Lead.status == status).count()
        funnel.append({"name": label, "value": count})

    # Active campaigns
    active_campaigns = db.query(Campaign).filter(Campaign.status == CampaignStatus.ACTIVE).count()

    return {
        "total_leads": total_leads,
        "qualified_leads": qualified,
        "contacted_leads": contacted,
        "meetings_scheduled": meetings,
        "response_rate": round(response_rate, 1),
        "funnel": funnel,
        "active_campaigns": active_campaigns,
    }
