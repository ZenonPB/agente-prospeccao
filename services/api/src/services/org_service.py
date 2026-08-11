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
    SalesRole,
    Lead,
    LeadActivityAction,
)
from src.services.lead_activity_service import log_activity

logger = logging.getLogger(__name__)


def is_full_access(member: OrganizationMember) -> bool:
    """True se o membro enxerga TODOS os leads da org.

    ANALYST/MANAGER (papel de venda) e owner/admin (papel administrativo)
    têm acesso total. CONSULTOR tem acesso restrito ao próprio funil (ou
    leads não atribuídos).
    """
    if member.sales_role in (SalesRole.ANALYST, SalesRole.MANAGER):
        return True
    return member.role in (OrganizationRole.OWNER, OrganizationRole.ADMIN)


def consultant_lead_scope(member: OrganizationMember, query):
    """Aplica o escopo de visibilidade de CONSULTOR à query de leads.

    CONSULTOR vê apenas:
    - leads atribuídos a ele (`assigned_to_id == member.user_id`), OU
    - leads não atribuídos (`assigned_to_id IS NULL` — pool para auto-atribuição).

    ANALYST/MANAGER/owner/admin não são filtrados (acesso total).
    """
    if is_full_access(member):
        return query
    entity = query.column_descriptions[0]["entity"]
    return query.filter(
        (entity.assigned_to_id == member.user_id) |
        (entity.assigned_to_id.is_(None))
    )


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


def create_organization(
    db: Session,
    name: str,
    owner_user: User,
    email_from: str | None = None,
) -> Organization:
    """Cria uma organização com o usuário como OWNER (roadmap-vendas 3.3.1).

    Usado para criar workspaces dedicados (ex.: "AlphaMek") além do pessoal do
    registro. O owner recebe `sales_role=MANAGER` (acesso total de leitura/BI)
    além do papel administrativo OWNER. Não faz commit (o caller decide).
    """
    org = Organization(
        id=uuid.uuid4(),
        name=name.strip(),
        slug=unique_slug(db, slugify(name)),
        email_from=email_from or None,
    )
    db.add(org)
    db.flush()
    db.add(OrganizationMember(
        organization_id=org.id,
        user_id=owner_user.id,
        role=OrganizationRole.OWNER,
        sales_role=SalesRole.MANAGER,
    ))
    db.flush()
    logger.info("Organização manual criada por user %s: %s", owner_user.id, org.slug)
    return org


def user_organization(db: Session, user: User) -> Organization | None:
    """Retorna a organização do usuário (primeira membership)."""
    member = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == user.id
    ).first()
    return member.organization if member else None


def unassign_user_leads_in_org(
    db: Session,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_user_id: uuid.UUID | None = None,
    reason: str = "Membro desligado da organização",
) -> int:
    """Desatribui todos os leads de um usuário dentro de uma organização (roadmap 3.3.3)."""
    leads = db.query(Lead).filter(
        Lead.organization_id == org_id,
        Lead.assigned_to_id == user_id,
    ).all()
    count = len(leads)
    for lead in leads:
        lead.assigned_to_id = None
        lead.assigned_at = None
        log_activity(
            db,
            lead,
            action=LeadActivityAction.UNASSIGNED,
            user_id=str(actor_user_id) if actor_user_id else None,
            detail=reason,
        )
    return count
