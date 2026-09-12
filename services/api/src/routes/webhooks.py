"""Webhooks públicos — inbound de e-mail e importação de leads.

Inbound de e-mail usa credencial por organização. A rota por token é o caminho
preferencial para provedores que só aceitam configurar URL; a rota legada exige
tanto o segredo global quanto ``X-Organization-Id`` e existe apenas para migração.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.dependencies import get_db
from src.db.models import Organization
from src.config.settings import settings
from src.middleware.rate_limit import limiter
from src.services.inbound_email_service import process_inbound_email
from src.services.inbound_token_service import resolve_organization_by_token
from src.services.webhook_import_service import import_leads_from_webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class InboundEmailPayload(BaseModel):
    from_email: str = Field(..., description="E-mail do remetente (resposta)")
    subject: str = Field("", description="Assunto da mensagem")
    body: str = Field("", description="Corpo da mensagem (texto puro)")


class WebhookImportLead(BaseModel):
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


def _process_inbound_for_org(
    db: Session,
    org: Organization,
    payload: InboundEmailPayload,
):
    return process_inbound_email(
        db,
        organization_id=org.id,
        from_email=payload.from_email,
        subject=payload.subject or "",
        body=payload.body or "",
    )


@router.post("/email/inbound/{token}")
@limiter.limit("60/minute")
def email_inbound_by_token(
    request: Request,
    token: str,
    payload: InboundEmailPayload,
    db: Session = Depends(get_db),
):
    """Inbound preferencial: token opaco identifica e autentica a organização."""
    org = resolve_organization_by_token(db, token)
    if org is None:
        # Resposta uniforme: não revela se token, org ou configuração existem.
        raise HTTPException(status_code=401, detail="Credencial de inbound inválida")
    return {"ok": True, **_process_inbound_for_org(db, org, payload)}


@router.post("/email/inbound")
@limiter.limit("60/minute")
def email_inbound_legacy(
    request: Request,
    payload: InboundEmailPayload,
    db: Session = Depends(get_db),
):
    """Compatibilidade temporária; exige segredo global + organização explícita."""
    if not settings.EMAIL_WEBHOOK_SECRET:
        raise HTTPException(status_code=404, detail="Webhook de inbound não configurado")
    if request.headers.get("X-Webhook-Secret") != settings.EMAIL_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Credencial de inbound inválida")

    raw_org_id = request.headers.get("X-Organization-Id")
    if not raw_org_id:
        raise HTTPException(status_code=401, detail="Credencial de inbound inválida")
    try:
        org_id = uuid.UUID(raw_org_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Credencial de inbound inválida")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None:
        raise HTTPException(status_code=401, detail="Credencial de inbound inválida")

    return {"ok": True, **_process_inbound_for_org(db, org, payload)}


@router.post("/import")
@limiter.limit("10/minute")
def webhook_import_leads(
    request: Request,
    payload: WebhookImportPayload,
    db: Session = Depends(get_db),
):
    """Importa leads via webhook (n8n, Make, Zapier, Apps Script, etc.)."""
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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Falha na importação via webhook")
        raise HTTPException(status_code=500, detail="Erro interno ao processar importação")
