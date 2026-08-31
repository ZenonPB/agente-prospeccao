"""Webhooks públicos — inbound de e-mail e importação de leads.

A rota não exige autenticação do usuário (o provedor de inbound/automação chama via
HTTP), mas valida um segredo compartilhado em `X-Webhook-Secret`
(settings.EMAIL_WEBHOOK_SECRET). Sem segredo configurado, responde 404.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.dependencies import get_db
from src.config.settings import settings
from src.middleware.rate_limit import limiter
from src.services.inbound_email_service import process_inbound_email
from src.services.webhook_import_service import import_leads_from_webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class InboundEmailPayload(BaseModel):
    from_email: str = Field(..., description="E-mail do remetente (resposta)")
    subject: str = Field("", description="Assunto da mensagem")
    body: str = Field("", description="Corpo da mensagem (texto puro)")


class WebhookImportLead(BaseModel):
    """Schema flexível para importação de leads — aceita aliases de campos."""
    name: str = Field(..., min_length=1, description="Nome/Razão social da empresa")
    website: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    city: str | None = None
    state: str | None = None
    address: str | None = None
    cnpj: str | None = None
    category: str | None = None
    contact_name: str | None = None
    linkedin: str | None = None
    instagram: str | None = None


class WebhookImportPayload(BaseModel):
    campaign_id: str = Field(..., description="ID da campanha (UUID)")
    leads: list[WebhookImportLead] = Field(..., min_length=1, max_length=500)


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
    return {"ok": True, **result}


@router.post("/import")
@limiter.limit("10/minute")
def webhook_import_leads(
    request: Request,
    payload: WebhookImportPayload,
    db: Session = Depends(get_db),
):
    """Importa leads via webhook (n8n, Make, Zapier, Apps Script, etc.).

    Requer header `X-Webhook-Secret` igual a `settings.EMAIL_WEBHOOK_SECRET`.
    O corpo deve conter `campaign_id` e array `leads` com objetos flexíveis.
    """
    if not settings.EMAIL_WEBHOOK_SECRET:
        raise HTTPException(status_code=404, detail="Webhook de importação não configurado")

    if request.headers.get("X-Webhook-Secret") != settings.EMAIL_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Segredo de webhook inválido")

    try:
        result = import_leads_from_webhook(
            db,
            campaign_id=payload.campaign_id,
            leads_data=[lead.model_dump() for lead in payload.leads],
        )
        return {"ok": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Falha na importação via webhook")
        raise HTTPException(status_code=500, detail="Erro interno ao processar importação")
