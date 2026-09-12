"""Serviço de convites com tokens de uso único armazenados por hash."""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.db.models import Invite, OrganizationMember, OrganizationRole, SalesRole, User

logger = logging.getLogger(__name__)


def hash_invite_token(token: str) -> str:
    """Gera a representação persistida do segredo sem armazená-lo em texto puro."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_invite_by_token(db: Session, token: str) -> Invite | None:
    """Resolve um convite pelo hash e migra convites legados sob demanda."""
    token_hash = hash_invite_token(token)
    invite = db.query(Invite).filter(Invite.token == token_hash).first()
    if invite:
        return invite

    legacy = db.query(Invite).filter(Invite.token == token).first()
    if legacy:
        legacy.token = token_hash
        db.flush()
        return legacy
    return None


def create_invite(
    db: Session,
    organization_id: uuid.UUID,
    email: str,
    invited_by_id: uuid.UUID,
    role: OrganizationRole = OrganizationRole.MEMBER,
    sales_role: SalesRole = SalesRole.CONSULTOR,
) -> Invite:
    """Cria ou renova um convite válido sem persistir o segredo reutilizável."""
    if role == OrganizationRole.OWNER:
        raise ValueError(
            "OWNER não pode ser concedido por convite; use transferência de propriedade",
        )

    normalized_email = email.strip().lower()
    now = datetime.now(timezone.utc)
    existing = db.query(Invite).filter(
        Invite.organization_id == organization_id,
        Invite.email == normalized_email,
        Invite.accepted_at.is_(None),
        Invite.expires_at > now,
    ).first()

    raw_token = secrets.token_urlsafe(32)
    persisted_token = hash_invite_token(raw_token)

    if existing:
        existing.token = persisted_token
        existing.role = role
        existing.sales_role = sales_role
        existing.invited_by_id = invited_by_id
        existing.expires_at = now + timedelta(days=7)
        db.flush()
        setattr(existing, "_raw_token", raw_token)
        logger.info("Convite pendente renovado na org %s", organization_id)
        return existing

    invite = Invite(
        id=uuid.uuid4(),
        organization_id=organization_id,
        email=normalized_email,
        token=persisted_token,
        role=role,
        sales_role=sales_role,
        invited_by_id=invited_by_id,
        expires_at=now + timedelta(days=7),
    )
    db.add(invite)
    db.flush()
    setattr(invite, "_raw_token", raw_token)
    logger.info("Convite criado para org %s", organization_id)
    return invite


def accept_invite(db: Session, token: str, user: User) -> OrganizationMember:
    """Aceita convite válido e cria membership somente na organização alvo."""
    from fastapi import HTTPException

    invite = get_invite_by_token(db, token)
    if not invite:
        raise HTTPException(status_code=404, detail="Convite não encontrado")

    if invite.accepted_at:
        raise HTTPException(status_code=400, detail="Convite já foi aceito")

    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Convite expirado")

    if invite.role == OrganizationRole.OWNER:
        raise HTTPException(
            status_code=400,
            detail="Convite de proprietário inválido. Use a transferência de propriedade.",
        )

    if invite.email.lower() != user.email.lower():
        raise HTTPException(status_code=403, detail="Este convite foi enviado para outro e-mail")

    existing_member = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == invite.organization_id,
        OrganizationMember.user_id == user.id,
    ).first()

    if existing_member:
        invite.accepted_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Convite %s aceito por usuário já membro", invite.id)
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
    logger.info("Convite %s aceito na org %s", invite.id, invite.organization_id)
    return member


def list_pending_invites(db: Session, organization_id: uuid.UUID) -> list[Invite]:
    return db.query(Invite).filter(
        Invite.organization_id == organization_id,
        Invite.accepted_at.is_(None),
        Invite.expires_at > datetime.now(timezone.utc),
    ).order_by(Invite.created_at.desc()).all()


def revoke_invite(db: Session, invite_id: uuid.UUID) -> None:
    invite = db.query(Invite).filter(Invite.id == invite_id).first()
    if invite and not invite.accepted_at:
        invite.expires_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Convite %s revogado", invite_id)
