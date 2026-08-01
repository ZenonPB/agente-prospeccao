from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.db.dependencies import get_db
from src.db.models import Lead, Campaign, LeadStatus, CampaignStatus, User, Organization
from src.auth.dependencies import get_current_user, get_user_organization

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
def get_metrics(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    base = db.query(Lead).filter(Lead.organization_id == _org.id)
    total_leads = base.count()
    qualified = base.filter(Lead.status == LeadStatus.QUALIFICADO).count()
    contacted = base.filter(Lead.status == LeadStatus.CONTATADO).count()
    meetings = base.filter(Lead.status == LeadStatus.REUNIAO_MARCADA).count()

    responded = base.filter(Lead.status == LeadStatus.RESPONDIDO).count()
    response_rate = (responded / contacted * 100) if contacted > 0 else 0

    funnel = []
    for status, label in [
        (LeadStatus.NOVO, "Novos"),
        (LeadStatus.ANALISADO, "Analisados"),
        (LeadStatus.QUALIFICADO, "Qualificados"),
        (LeadStatus.CONTATADO, "Contatados"),
        (LeadStatus.RESPONDIDO, "Responderam"),
        (LeadStatus.REUNIAO_MARCADA, "Reuniões"),
    ]:
        count = base.filter(Lead.status == status).count()
        funnel.append({"stage": label, "count": count})

    active_campaigns = db.query(Campaign).filter(
        Campaign.status == CampaignStatus.ACTIVE,
        Campaign.organization_id == _org.id,
    ).count()

    return {
        "total_leads": total_leads,
        "qualified_leads": qualified,
        "contacted_leads": contacted,
        "meetings_scheduled": meetings,
        "response_rate": round(response_rate, 1),
        "funnel": funnel,
        "active_campaigns": active_campaigns,
    }
