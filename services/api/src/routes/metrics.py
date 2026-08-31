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

    status_counts = dict(
        base.with_entities(Lead.status, func.count(Lead.id))
        .group_by(Lead.status)
        .all()
    )
    total_leads = sum(status_counts.values())
    qualified = status_counts.get(LeadStatus.QUALIFICADO, 0)
    contacted = status_counts.get(LeadStatus.CONTATADO, 0)
    meetings = status_counts.get(LeadStatus.REUNIAO_MARCADA, 0)
    responded = status_counts.get(LeadStatus.RESPONDIDO, 0)
    response_rate = (responded / contacted * 100) if contacted > 0 else 0

    _FUNNEL_MAP = [
        (LeadStatus.NOVO, "Novos"),
        (LeadStatus.ANALISADO, "Analisados"),
        (LeadStatus.QUALIFICADO, "Qualificados"),
        (LeadStatus.CONTATADO, "Contatados"),
        (LeadStatus.RESPONDIDO, "Responderam"),
        (LeadStatus.REUNIAO_MARCADA, "Reuniões"),
    ]
    funnel = [{"stage": label, "count": status_counts.get(s, 0)} for s, label in _FUNNEL_MAP]

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
