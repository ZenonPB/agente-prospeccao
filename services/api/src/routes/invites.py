"""Rotas de convites — criar, listar, aceitar, revogar.

Fase A4/A5: owner/admin convidam usuários para sua organização por e-mail.
O convite gera um token que o convidado usa para aceitar.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from typing import List

from src.db.dependencies import get_db
from src.db.models import (
    User,
    Organization,
    OrganizationMember,
    Invite,
    OrganizationRole,
    SalesRole,
)
from src.auth.dependencies import (
    get_current_user,
    get_user_organization,
    require_org_admin,
)
from src.services import invite_service

router = APIRouter(tags=["invites"])


class CreateInviteRequest(BaseModel):
    email: EmailStr = Field(..., description="E-mail do convidado")
    role: OrganizationRole = Field(
        OrganizationRole.MEMBER,
        description="Papel administrativo (OWNER/ADMIN/MEMBER)"
    )
    sales_role: SalesRole = Field(
        SalesRole.CONSULTOR,
        description="Papel de venda (CONSULTOR/ANALYST/MANAGER)"
    )


class AcceptInviteRequest(BaseModel):
    token: str = Field(..., description="Token do convite")


def _invite_dict(inv: Invite) -> dict:
    return {
        "id": str(inv.id),
        "email": inv.email,
        "role": inv.role.value if inv.role else None,
        "sales_role": inv.sales_role.value if inv.sales_role else None,
        "invited_by_id": str(inv.invited_by_id),
        "invited_by_name": inv.invited_by.name if inv.invited_by else None,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "expires_at": inv.expires_at.isoformat() if inv.expires_at else None,
        "accepted_at": inv.accepted_at.isoformat() if inv.accepted_at else None,
    }


@router.post("/orgs/{org_id}/invites")
def create_invite(
    org_id: str,
    body: CreateInviteRequest,
    db: Session = Depends(get_db),
    org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_org_admin),
):
    """Cria um convite para um e-mail na organização (owner/admin only).
    
    Envia e-mail com token de aceitação. Se o convite já existe (pendente e
    não expirado), retorna o existente sem duplicar.
    """
    if str(org.id) != org_id or str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    
    existing_user = db.query(User).filter(User.email == body.email.lower()).first()
    if existing_user:
        existing_member = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == existing_user.id,
        ).first()
        if existing_member:
            raise HTTPException(
                status_code=400,
                detail="Este usuário já é membro da organização"
            )
    
    invite = invite_service.create_invite(
        db=db,
        organization_id=org.id,
        email=body.email,
        invited_by_id=actor.user_id,
        role=body.role,
        sales_role=body.sales_role,
    )
    db.commit()
    db.refresh(invite)
    
    return _invite_dict(invite)


@router.get("/orgs/{org_id}/invites")
def list_invites(
    org_id: str,
    db: Session = Depends(get_db),
    org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_org_admin),
):
    """Lista convites pendentes da organização (owner/admin only)."""
    if str(org.id) != org_id or str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    
    invites = invite_service.list_pending_invites(db, org.id)
    return {"invites": [_invite_dict(inv) for inv in invites]}


@router.post("/invites/accept")
def accept_invite(
    body: AcceptInviteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Aceita um convite por token.
    
    O usuário deve estar autenticado e o e-mail do convite deve bater com
    o e-mail do usuário. Cria a membership na organização do convite.
    """
    member = invite_service.accept_invite(db, body.token, user)
    
    return {
        "message": "Convite aceito com sucesso",
        "organization": {
            "id": str(member.organization_id),
            "name": member.organization.name if member.organization else None,
            "slug": member.organization.slug if member.organization else None,
        },
        "membership": {
            "role": member.role.value if member.role else None,
            "sales_role": member.sales_role.value if member.sales_role else None,
        },
    }


@router.delete("/orgs/{org_id}/invites/{invite_id}")
def revoke_invite(
    org_id: str,
    invite_id: str,
    db: Session = Depends(get_db),
    org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_org_admin),
):
    """Revoga um convite pendente (owner/admin only)."""
    if str(org.id) != org_id or str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    
    invite = db.query(Invite).filter(
        Invite.id == invite_id,
        Invite.organization_id == org.id,
    ).first()
    
    if not invite:
        raise HTTPException(status_code=404, detail="Convite não encontrado")
    
    invite_service.revoke_invite(db, invite.id)
    
    return {"message": "Convite revogado com sucesso"}
