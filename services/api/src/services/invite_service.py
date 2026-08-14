"""Serviço de convites — criação, validação, aceite.

Permite que owner/admin convidem usuários para sua organização
por e-mail. O token do convite é enviado por e-mail e usado na aceitação.
"""
import secrets
import uuid
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.db.models import (
    User,
    Organization,
    OrganizationMember,
    Invite,
    OrganizationRole,
    SalesRole,
)

logger = logging.getLogger(__name__)


def create_invite(
    db: Session,
    organization_id: uuid.UUID,
    email: str,
    invited_by_id: uuid.UUID,
    role: OrganizationRole = OrganizationRole.MEMBER,
    sales_role: SalesRole = SalesRole.CONSULTOR,
) -> Invite:
    """Cria um convite para um e-mail na organização.
    
    Se o e-mail já tiver um convite pendente (não aceito e não expirado),
    retorna o existente. Convites expiram em 7 dias.
    """
    existing = db.query(Invite).filter(
        Invite.organization_id == organization_id,
        Invite.email == email.lower(),
        Invite.accepted_at.is_(None),
        Invite.expires_at > datetime.now(timezone.utc),
    ).first()
    
    if existing:
        logger.info("Convite pendente já existe para %s na org %s", email, organization_id)
        return existing

    token = secrets.token_urlsafe(32)
    invite = Invite(
        id=uuid.uuid4(),
        organization_id=organization_id,
        email=email.lower(),
        token=token,
        role=role,
        sales_role=sales_role,
        invited_by_id=invited_by_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    db.flush()
    logger.info("Convite criado: %s → org %s (token: %s...)", email, organization_id, token[:8])
    return invite


def accept_invite(db: Session, token: str, user: User) -> OrganizationMember:
    """Aceita um convite por token.
    
    Valida:
    - Token existe e não expirou
    - E-mail do token bate com o e-mail do usuário
    - Usuário ainda não é membro da organização
    
    Retorna a membership criada ou levanta HTTPException.
    """
    from fastapi import HTTPException
    
    invite = db.query(Invite).filter(Invite.token == token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Convite não encontrado")
    
    if invite.accepted_at:
        raise HTTPException(status_code=400, detail="Convite já foi aceito")
    
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Convite expirado")
    
    if invite.email.lower() != user.email.lower():
        raise HTTPException(
            status_code=403,
            detail="Este convite foi enviado para outro e-mail"
        )
    
    existing_member = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == invite.organization_id,
        OrganizationMember.user_id == user.id,
    ).first()
    
    if existing_member:
        invite.accepted_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Convite %s aceito (usuário já era membro)", invite.id)
        return existing_member
    
    member = OrganizationMember(
        organization_id=invite.organization_id,
        user_id=user.id,
        role=invite.role,
        sales_role=invite.sales_role,
    )
    db.add(member)
    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(member)
    
    logger.info(
        "Convite %s aceito: user %s → org %s (role=%s, sales_role=%s)",
        invite.id,
        user.id,
        invite.organization_id,
        invite.role.value,
        invite.sales_role.value,
    )
    return member


def list_pending_invites(db: Session, organization_id: uuid.UUID) -> list[Invite]:
    """Lista convites pendentes (não aceitos e não expirados) da organização."""
    return db.query(Invite).filter(
        Invite.organization_id == organization_id,
        Invite.accepted_at.is_(None),
        Invite.expires_at > datetime.now(timezone.utc),
    ).order_by(Invite.created_at.desc()).all()


def revoke_invite(db: Session, invite_id: uuid.UUID) -> None:
    """Revoga um convite (marca como expirado imediatamente)."""
    invite = db.query(Invite).filter(Invite.id == invite_id).first()
    if invite and not invite.accepted_at:
        invite.expires_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Convite %s revogado", invite_id)
