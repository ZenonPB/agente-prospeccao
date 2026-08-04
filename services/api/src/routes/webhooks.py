"""Webhooks públicos — inbound de e-mail (item 3.3).

A rota não exige autenticação do usuário (o provedor de inbound chama via
HTTP), mas valida um segredo compartilhado em `X-Webhook-Secret`
(settings.EMAIL_WEBHOOK_SECRET). Sem segredo configurado, responde 404.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.dependencies import get_db
from src.config.settings import settings
from src.services.inbound_email_service import process_inbound_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class InboundEmailPayload(BaseModel):
    from_email: str = Field(..., description="E-mail do remetente (resposta)")
    subject: str = Field("", description="Assunto da mensagem")
    body: str = Field("", description="Corpo da mensagem (texto puro)")


@router.post("/email/inbound")
def email_inbound(
    request: Request,
    payload: InboundEmailPayload,
    db: Session = Depends(get_db),
):
    """Recebe resposta/STOP de e-mail do provedor de inbound (Postmark/SendGrid)."""
    if not settings.EMAIL_WEBHOOK_SECRET:
        raise HTTPException(status_code=404, detail="Webhook de inbound não configurado")

    if request.headers.get("X-Webhook-Secret") != settings.EMAIL_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Segredo de webhook inválido")

    result = process_inbound_email(
        db,
        from_email=payload.from_email,
        subject=payload.subject or "",
        body=payload.body or "",
    )
    # Sem lead correspondente → 200 vazio (provedor não deve re-tentar).
    return {"ok": True, **result}
