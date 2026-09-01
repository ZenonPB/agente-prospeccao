"""Rotas de notificações in-app.

Permite listar, marcar como lida e marcar todas como lidas.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from src.db.dependencies import get_db
from src.db.models import Notification, Organization, User, OrganizationMember
from src.auth.dependencies import get_current_user, get_user_organization

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    id: str
    notification_type: str
    title: str
    message: Optional[str]
    lead_id: Optional[str]
    is_read: bool
    created_at: str


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int
    total: int


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Lista notificações do usuário na organização ativa."""
    query = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.organization_id == _org.id,
    )
    if unread_only:
        query = query.filter(Notification.is_read == False)

    total = query.count()
    unread_count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.organization_id == _org.id,
        Notification.is_read == False,
    ).count()

    items = query.order_by(Notification.created_at.desc()).limit(limit).all()

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=str(n.id),
                notification_type=n.notification_type.value,
                title=n.title,
                message=n.message,
                lead_id=str(n.lead_id) if n.lead_id else None,
                is_read=n.is_read,
                created_at=n.created_at.isoformat() if n.created_at else "",
            )
            for n in items
        ],
        unread_count=unread_count,
        total=total,
    )


class MarkReadResponse(BaseModel):
    success: bool
    unread_count: int


@router.patch("/{notification_id}/read", response_model=MarkReadResponse)
def mark_read(
    notification_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Marca uma notificação como lida."""
    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user.id,
        Notification.organization_id == _org.id,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")

    n.is_read = True
    db.commit()

    unread_count = db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.organization_id == _org.id,
        Notification.is_read == False,
    ).count()

    return MarkReadResponse(success=True, unread_count=unread_count)


@router.patch("/read-all", response_model=MarkReadResponse)
def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Marca todas as notificações como lidas."""
    db.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.organization_id == _org.id,
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()

    return MarkReadResponse(success=True, unread_count=0)
