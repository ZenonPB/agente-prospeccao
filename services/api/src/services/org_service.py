"""Serviço de organização — criação de workspace e helpers de acesso.

Fase A (multi-tenant): concentra a lógica de criação de organização pessoal
no registro e helpers de verificação de acesso usados nas rotas.
"""
import re
import uuid
import logging

from sqlalchemy.orm import Session

from src.db.models import (
    User,
    Organization,
    OrganizationMember,
    OrganizationRole,
)

logger = logging.getLogger(__name__)


def slugify(value: str) -> str:
    """Gera um slug simples a partir de nome/email."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:120] or "workspace"


def unique_slug(db: Session, base: str) -> str:
    """Retorna um slug único (sufixa -2, -3... até achar livre)."""
    slug = base
    i = 2
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base}-{i}"
        i += 1
    return slug


def create_personal_organization(db: Session, user: User) -> Organization:
    """Cria o workspace pessoal do usuário + membership owner.

    Chamado no registro. Idempotente por usuário (se já tiver membership
    em alguma org, retorna a primeira em vez de duplicar).
    """
    existing = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == user.id
    ).first()
    if existing:
        return existing.organization

    name = f"{user.name}'s workspace"
    org = Organization(
        id=uuid.uuid4(),
        name=name,
        slug=unique_slug(db, slugify(user.name or user.email.split("@")[0])),
    )
    db.add(org)
    db.flush()

    db.add(OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role=OrganizationRole.OWNER,
    ))
    db.flush()
    logger.info("Organização pessoal criada para user %s: %s", user.id, org.slug)
    return org


def user_organization(db: Session, user: User) -> Organization | None:
    """Retorna a organização do usuário (primeira membership)."""
    member = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == user.id
    ).first()
    return member.organization if member else None
