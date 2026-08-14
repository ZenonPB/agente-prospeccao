"""Serviço de auditoria de membros e acessos da organização.

Grava `OrgAuditLog` para eventos administrativos (convite criado/aceito/
revogado, papel alterado, membro removido/saída, transferência de ownership,
chave BYOK alterada, metas de venda). Dá rastreabilidade à diretoria.
Nunca grava valor de secret — só o `key_name`.
"""
import logging
from typing import List, Optional, Union

from sqlalchemy.orm import Session

from src.db.models import (
    OrgAuditEvent,
    OrgAuditLog,
    OrganizationMember,
    User,
)

logger = logging.getLogger(__name__)


def _actor_meta(actor: Optional[Union[OrganizationMember, User]]) -> tuple:
    """Resolve (actor_id, name, email) de um membro ou usuário."""
    if actor is None:
        return None, None, None
    if hasattr(actor, "user_id") and hasattr(actor, "user"):
        return actor.user_id, actor.user.name if actor.user else None, actor.user.email if actor.user else None
    return actor.id, actor.name, actor.email


def log_org_event(
    db: Session,
    organization_id,
    event: OrgAuditEvent,
    actor: Optional[Union[OrganizationMember, User]] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[str] = None,
) -> OrgAuditLog:
    """Registra um evento administrativo na auditoria da org.

    Args:
        db: Sessão ativa.
        organization_id: Organização afetada (UUID).
        event: Tipo de evento (OrgAuditEvent).
        actor: Quem executou (member ou user; nullable p/ fluxos automáticos).
        target_type: "member" | "invite" | "secret" | "target" | "org".
        target_id: Identificador do alvo (id/email/key_name — nunca valor de secret).
        detail: Payload descritivo livre (ex.: "CONTADOR->MANAGER"; "key=GROQ_API_KEY").

    Returns:
        OrgAuditLog criada (não commita — quem chama decide o commit).
    """
    actor_id, actor_name, actor_email = _actor_meta(actor)
    entry = OrgAuditLog(
        organization_id=organization_id,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_email=actor_email,
        event=event,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    db.add(entry)
    return entry


def list_org_audit(
    db: Session,
    organization_id,
    event: Optional[OrgAuditEvent] = None,
    limit: int = 50,
) -> List[OrgAuditLog]:
    """Lista os eventos de auditoria da org, do mais recente para o mais antigo."""
    query = db.query(OrgAuditLog).filter(OrgAuditLog.organization_id == organization_id)
    if event is not None:
        query = query.filter(OrgAuditLog.event == event)
    return query.order_by(OrgAuditLog.created_at.desc()).limit(limit).all()