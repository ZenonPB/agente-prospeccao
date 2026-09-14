"""Listagem operacional do Sales Operating System.

Separada das rotas de comandos para manter filtros server-side e permitir que
visões salvas do CRM sejam restauradas sem reutilizar paginação efêmera.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.crm_models import LeadCrmMetadata
from src.auth.dependencies import get_user_membership, get_user_organization
from src.db.dependencies import get_db
from src.db.models import Campaign, Lead, LeadPriority, LeadStatus, Organization, OrganizationMember
from src.services.org_service import consultant_lead_scope

router = APIRouter(prefix="/operating", tags=["crm-operating"])


def _enum_value(value):
    return getattr(value, "value", value)


@router.get("/leads")
def operating_leads(
    search: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, max_length=32),
    priority: str | None = Query(default=None, max_length=16),
    campaign_id: str | None = Query(default=None, max_length=64),
    assigned: str | None = Query(default=None, max_length=64),
    min_score: int | None = Query(default=None, ge=0, le=100),
    archived: str = Query(default="active", pattern="^(active|archived|all)$"),
    tag: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    db: Session = Depends(get_db),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    query = db.query(Lead, LeadCrmMetadata).outerjoin(
        LeadCrmMetadata,
        (LeadCrmMetadata.lead_id == Lead.id) & (LeadCrmMetadata.organization_id == org.id),
    ).filter(Lead.organization_id == org.id)

    # consultant_lead_scope opera sobre Query[Lead]. Reaplicamos a mesma regra
    # através do conjunto de ids visíveis para manter a junção tipada e fail-closed.
    visible_ids = consultant_lead_scope(
        member,
        db.query(Lead.id).filter(Lead.organization_id == org.id),
    ).subquery()
    query = query.filter(Lead.id.in_(visible_ids))

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Lead.company_name.ilike(pattern), Lead.category.ilike(pattern), Lead.city.ilike(pattern)))
    if status:
        try:
            query = query.filter(Lead.status == LeadStatus(status))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="status inválido") from exc
    if priority:
        try:
            query = query.filter(Lead.priority == LeadPriority(priority))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="priority inválida") from exc
    if campaign_id:
        campaign = db.query(Campaign.id).filter(Campaign.id == campaign_id, Campaign.organization_id == org.id).first()
        if not campaign:
            raise HTTPException(status_code=422, detail="campaign_id inválido para o workspace")
        query = query.filter(Lead.campaign_id == campaign_id)
    if assigned == "me":
        query = query.filter(Lead.assigned_to_id == member.user_id)
    elif assigned:
        query = query.filter(Lead.assigned_to_id == assigned)
    if min_score is not None:
        query = query.filter(Lead.qualification_score >= min_score)
    if archived == "active":
        query = query.filter(or_(LeadCrmMetadata.id.is_(None), LeadCrmMetadata.archived_at.is_(None)))
    elif archived == "archived":
        query = query.filter(LeadCrmMetadata.archived_at.is_not(None))
    if tag:
        query = query.filter(LeadCrmMetadata.tags.contains([tag]))

    total = query.count()
    rows = query.order_by(
        Lead.qualification_score.desc().nullslast(),
        Lead.updated_at.desc(),
        Lead.id.asc(),
    ).offset(offset).limit(limit).all()
    return {
        "items": [
            {
                "id": str(lead.id),
                "company_name": lead.company_name,
                "city": lead.city,
                "state": lead.state,
                "status": _enum_value(lead.status),
                "priority": _enum_value(lead.priority),
                "negotiation_stage": _enum_value(lead.negotiation_stage),
                "qualification_score": lead.qualification_score,
                "value": float(lead.value) if lead.value is not None else None,
                "campaign_id": str(lead.campaign_id) if lead.campaign_id else None,
                "assigned_to_id": str(lead.assigned_to_id) if lead.assigned_to_id else None,
                "next_action_at": lead.next_action_at.isoformat() if lead.next_action_at else None,
                "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
                "tags": list(metadata.tags or []) if metadata else [],
                "archived_at": metadata.archived_at.isoformat() if metadata and metadata.archived_at else None,
            }
            for lead, metadata in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
