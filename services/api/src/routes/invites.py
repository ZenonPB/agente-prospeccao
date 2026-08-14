"""Rotas de convites — criar, listar, aceitar, revogar.

Owner/admin convidam usuários para sua organização por e-mail.
O convite gera um token que o convidado usa para aceitar.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import List
from datetime import datetime, timezone

from src.db.dependencies import get_db
from src.db.models import (
    User,
    Organization,
    OrganizationMember,
    Invite,
    OrganizationRole,
    SalesRole,
    OrgAuditEvent,
)
from src.auth.dependencies import (
    get_current_user,
    get_user_organization,
    require_org_admin,
)
from src.auth.security import hash_password, create_access_token
from src.config.settings import settings
from src.services import invite_service
from src.services.email_service import send_invite_email
from src.services.org_audit_service import log_org_event

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

    @field_validator("role", mode="before")
    @classmethod
    def _coerce_org_role(cls, v):
        """Aceita tanto o valor do enum no banco (owner/admin/member) quanto o
        nome (OWNER/ADMIN/MEMBER) — o frontend envia maiúsculo (tipo OrgRole)."""
        if isinstance(v, str):
            v = v.strip()
            try:
                return OrganizationRole(v.lower())
            except ValueError:
                return OrganizationRole[v.upper()]
        return v


class AcceptInviteRequest(BaseModel):
    token: str = Field(..., description="Token do convite")


class AcceptRegisterRequest(BaseModel):
    """Cadastro + aceite no mesmo fluxo.

    Para quem ainda não tem conta: cria o usuário com o e-mail do convite e já
    o adiciona à organização em um único passo.
    """
    token: str = Field(..., description="Token do convite")
    name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


def _invite_dict(inv: Invite) -> dict:
    return {
        "id": str(inv.id),
        "email": inv.email,
        "role": inv.role.name if inv.role else None,
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
    log_org_event(
        db, org.id, OrgAuditEvent.INVITE_CREATED, actor=actor,
        target_type="invite", target_id=body.email.lower(),
        detail=f"role={body.role.value} sales_role={body.sales_role.value}",
    )
    db.commit()
    db.refresh(invite)

    invited_by = db.query(User).filter(User.id == actor.user_id).first()
    accept_link = f"{settings.APP_BASE_URL}/aceitar-convite?token={invite.token}"
    send_invite_email(
        to_email=invite.email,
        org_name=org.name or "nova organização",
        accept_link=accept_link,
        invited_by_name=invited_by.name if invited_by else "",
    )
    
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
    log_org_event(
        db, member.organization_id, OrgAuditEvent.INVITE_ACCEPTED, actor=user,
        target_type="invite", target_id=user.email,
    )
    db.commit()
    return {
        "message": "Convite aceito com sucesso",
        "organization": {
            "id": str(member.organization_id),
            "name": member.organization.name if member.organization else None,
            "slug": member.organization.slug if member.organization else None,
        },
        "membership": {
            "role": member.role.name if member.role else None,
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
    log_org_event(
        db, org.id, OrgAuditEvent.INVITE_REVOKED, actor=actor,
        target_type="invite", target_id=invite.email,
    )
    db.commit()
    return {"message": "Convite revogado com sucesso"}


@router.get("/invites/check")
def check_invite(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """Resolve um convite por token (público, sem auth) para a página de aceite.

    Informa o e-mail do convite, a organização e se já existe conta — o
    frontend decide entre login ou cadastro no próprio aceite.
    """
    invite = db.query(Invite).filter(Invite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Convite não encontrado")

    existing = db.query(User).filter(User.email == invite.email).first()
    expired = invite.expires_at < datetime.now(timezone.utc)
    return {
        "email": invite.email,
        "organization": {
            "id": str(invite.organization_id),
            "name": invite.organization.name if invite.organization else None,
            "slug": invite.organization.slug if invite.organization else None,
        },
        "has_account": existing is not None,
        "accepted": invite.accepted_at is not None,
        "expired": expired,
    }


@router.post("/invites/accept-register")
def accept_register(
    body: AcceptRegisterRequest,
    db: Session = Depends(get_db),
):
    """Cadastra o convidado + aceita o convite em um único passo.

    Válido apenas quando o e-mail do convite ainda não tem conta. Cria o
    usuário (sem workspace pessoal — ele cai direto na org do convite) e já
    retorna um token JWT para auto-login.
    """
    invite = db.query(Invite).filter(Invite.token == body.token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Convite não encontrado")
    if invite.accepted_at:
        raise HTTPException(status_code=400, detail="Convite já foi aceito")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Convite expirado")

    existing = db.query(User).filter(User.email == invite.email).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Já existe uma conta com este e-mail. Faça login e aceite o convite.",
        )

    user = User(
        name=body.name,
        email=invite.email,
        password_hash=hash_password(body.password),
        role="SALES",
    )
    db.add(user)
    db.flush()

    member = invite_service.accept_invite(db, body.token, user)
    log_org_event(
        db, member.organization_id, OrgAuditEvent.INVITE_ACCEPTED, actor=user,
        target_type="invite", target_id=user.email,
    )
    db.commit()
    token = create_access_token({"sub": str(user.id), "email": user.email})

    return {
        "message": "Conta criada e convite aceito com sucesso",
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
        },
        "token": token,
        "organization": {
            "id": str(member.organization_id),
            "name": member.organization.name if member.organization else None,
            "slug": member.organization.slug if member.organization else None,
        },
        "membership": {
            "role": member.role.name if member.role else None,
            "sales_role": member.sales_role.value if member.sales_role else None,
        },
    }
