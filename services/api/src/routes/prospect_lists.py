"""Listas operacionais de oportunidades usadas por vendedores e workflows."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.crm_models import ProspectList, ProspectListMember
from src.auth.dependencies import get_current_user, get_user_organization, require_analyst
from src.db.dependencies import get_db
from src.db.models import Lead, Organization, OrganizationMember, User

router = APIRouter(prefix="/prospect-lists", tags=["prospect-lists"])


class ProspectListCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    description: str | None = Field(None, max_length=2000)


class ProspectListMemberCreate(BaseModel):
    lead_id: str


def _list_dict(row: ProspectList, members: int = 0) -> dict:
    return {"id": str(row.id), "name": row.name, "description": row.description, "active": row.active, "member_count": members, "created_at": row.created_at.isoformat() if row.created_at else None}


@router.get("")
def list_prospect_lists(db: Session = Depends(get_db), _member: OrganizationMember = Depends(require_analyst()), org: Organization = Depends(get_user_organization)):
    rows = db.query(ProspectList).filter(ProspectList.organization_id == org.id, ProspectList.active.is_(True)).order_by(ProspectList.name.asc()).all()
    counts = dict(db.query(ProspectListMember.list_id, func.count(ProspectListMember.id)).filter(ProspectListMember.organization_id == org.id).group_by(ProspectListMember.list_id).all())
    return {"items": [_list_dict(row, int(counts.get(row.id, 0))) for row in rows]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_prospect_list(body: ProspectListCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user), _member: OrganizationMember = Depends(require_analyst()), org: Organization = Depends(get_user_organization)):
    name = body.name.strip()
    if db.query(ProspectList.id).filter(ProspectList.organization_id == org.id, ProspectList.name == name).first():
        raise HTTPException(status_code=409, detail="Já existe uma lista com esse nome")
    row = ProspectList(organization_id=org.id, name=name, description=body.description.strip() if body.description else None, created_by_id=user.id)
    db.add(row); db.commit(); db.refresh(row)
    return _list_dict(row)


@router.post("/{list_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(list_id: str, body: ProspectListMemberCreate, db: Session = Depends(get_db), _member: OrganizationMember = Depends(require_analyst()), org: Organization = Depends(get_user_organization)):
    target = db.query(ProspectList).filter(ProspectList.id == list_id, ProspectList.organization_id == org.id, ProspectList.active.is_(True)).first()
    if not target:
        raise HTTPException(status_code=404, detail="Lista não encontrada")
    lead = db.query(Lead).filter(Lead.id == body.lead_id, Lead.organization_id == org.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada")
    existing = db.query(ProspectListMember).filter(ProspectListMember.list_id == target.id, ProspectListMember.lead_id == lead.id).first()
    if existing:
        return {"id": str(existing.id), "list_id": str(target.id), "lead_id": str(lead.id), "created": False}
    row = ProspectListMember(organization_id=org.id, list_id=target.id, lead_id=lead.id, source="manual")
    db.add(row); db.commit(); db.refresh(row)
    return {"id": str(row.id), "list_id": str(target.id), "lead_id": str(lead.id), "created": True}


@router.get("/{list_id}/members")
def list_members(list_id: str, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), _member: OrganizationMember = Depends(require_analyst()), org: Organization = Depends(get_user_organization)):
    target = db.query(ProspectList).filter(ProspectList.id == list_id, ProspectList.organization_id == org.id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Lista não encontrada")
    rows = db.query(ProspectListMember, Lead).join(Lead, Lead.id == ProspectListMember.lead_id).filter(ProspectListMember.organization_id == org.id, ProspectListMember.list_id == target.id, Lead.organization_id == org.id).order_by(ProspectListMember.created_at.desc()).limit(limit).all()
    return {"items": [{"id": str(member.id), "lead_id": str(lead.id), "company_name": lead.company_name, "status": lead.status.value if getattr(lead.status, "value", None) else str(lead.status), "created_at": member.created_at.isoformat() if member.created_at else None} for member, lead in rows]}
