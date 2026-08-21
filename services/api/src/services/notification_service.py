"""Notification service — cria e consulta notificações in-app.

Notificações são criadas em background quando eventos relevantes
acontecem (lead responde, lead atribuído, alerta SLA).
O frontend consulta via polling e exibe badge no header/sidebar.
"""
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.db.models import (
    Notification, NotificationType,
    Lead, LeadStatus,
    Organization, OrganizationMember,
)

logger = logging.getLogger(__name__)


def create_lead_responded_notification(
    db: Session,
    lead: Lead,
    organization_id: UUID,
) -> None:
    """Cria notificação quando um lead responde (status → RESPONDIDO).

    A notificação vai para o consultor atribuído ao lead.
    """
    if not lead.assigned_to_id:
        logger.debug("Lead %s respondeu mas não tem atribuição — notificação pulada", lead.id)
        return

    notification = Notification(
        user_id=lead.assigned_to_id,
        organization_id=organization_id,
        notification_type=NotificationType.LEAD_RESPONDED,
        title=f"{lead.company_name} respondeu",
        message=f"O lead {lead.company_name} respondeu ao e-mail. Clique para ver a resposta.",
        lead_id=lead.id,
        is_read=False,
    )
    db.add(notification)
    logger.info("Notificação criada: lead %s respondeu (user %s)", lead.id, lead.assigned_to_id)


def create_lead_assigned_notification(
    db: Session,
    lead: Lead,
    organization_id: UUID,
    assigned_to_id: UUID,
) -> None:
    """Cria notificação quando um lead é atribuído a um consultor."""
    notification = Notification(
        user_id=assigned_to_id,
        organization_id=organization_id,
        notification_type=NotificationType.LEAD_ASSIGNED,
        title=f"{lead.company_name} atribuído a você",
        message=f"O lead {lead.company_name} foi atribuído a você para acompanhamento.",
        lead_id=lead.id,
        is_read=False,
    )
    db.add(notification)
    logger.info("Notificação criada: lead %s atribuído a user %s", lead.id, assigned_to_id)


def mark_notification_read(db: Session, notification_id: UUID, user_id: UUID) -> bool:
    """Marca uma notificação como lida. Retorna True se encontrou."""
    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user_id,
    ).first()
    if not n:
        return False
    n.is_read = True
    db.commit()
    return True


def mark_all_notifications_read(db: Session, user_id: UUID, organization_id: UUID) -> int:
    """Marca todas as notificações não lidas como lidas. Retorna qtd."""
    count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.organization_id == organization_id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return count
