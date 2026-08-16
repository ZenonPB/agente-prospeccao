"""Webhook outbound genérico por organização.

Dispara eventos para `Organization.webhook_url` quando configurado. Os
eventos têm o formato:

    POST {webhook_url}
    Content-Type: application/json
    X-Webhook-Secret: {secret}
    X-Webhook-Event: lead.created | lead.status_changed | conversion.created

    {"event": "<event>", "data": {...}}

A entrega é fire-and-forget via `BackgroundTasks` do FastAPI (não bloqueia
a request) com retry simples de 3x e backoff (0.5s, 1s, 2s). Falhas são
logadas; não geram exceções no caller.

Função pública:
- `enqueue_webhook(background_tasks, db, organization_id, event, data)`:
  lê a org, valida `webhook_url`, agenda o disparo.
- `_post_webhook` (interno): faz o POST real (httpx.AsyncClient).
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from src.db.models import Organization

logger = logging.getLogger(__name__)

RETRY_DELAYS = (0.5, 1.0, 2.0)
TIMEOUT = 5.0


def build_webhook_payload(event: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Monta o body enviado ao consumidor (pura — testável sem rede)."""
    return {
        "event": event,
        "data": data,
    }


def build_webhook_headers(secret: Optional[str], event: str) -> Dict[str, str]:
    """Monta os headers — inclui `X-Webhook-Secret` apenas se há segredo."""
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Event": event,
    }
    if secret:
        headers["X-Webhook-Secret"] = secret
    return headers


async def _post_webhook(
    url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
) -> bool:
    """POST com retry simples. Retorna True no 2xx, False em qualquer falha."""
    body = json.dumps(payload, default=str)
    for attempt, delay in enumerate((0.0,) + RETRY_DELAYS):
        if delay:
            await asyncio.sleep(delay)
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                r = await client.post(url, content=body, headers=headers)
            if 200 <= r.status_code < 300:
                return True
            logger.warning(
                "Webhook %s respondeu %s na tentativa %d: %s",
                url, r.status_code, attempt + 1, r.text[:200],
            )
        except httpx.RequestError as e:
            logger.warning(
                "Webhook %s falhou na tentativa %d: %s",
                url, attempt + 1, e,
            )
    return False


def enqueue_webhook(
    background_tasks: BackgroundTasks,
    db: Session,
    organization_id: Any,
    event: str,
    data: Dict[str, Any],
) -> bool:
    """Agenda o disparo do webhook via `BackgroundTasks`.

    Retorna True se agendou (org tem `webhook_url` configurado), False caso
    contrário. Não bloqueia a request — o POST roda em background.
    """
    if not organization_id:
        return False
    org = (
        db.query(Organization)
        .filter(Organization.id == organization_id)
        .first()
    )
    if not org or not org.webhook_url:
        return False
    payload = build_webhook_payload(event, data)
    headers = build_webhook_headers(org.webhook_secret, event)
    background_tasks.add_task(
        _dispatch_webhook, str(org.webhook_url), payload, headers,
    )
    return True


async def _dispatch_webhook(
    url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
) -> None:
    """Wrapper que executa o POST e loga o resultado final."""
    ok = await _post_webhook(url, payload, headers)
    if ok:
        logger.info("Webhook entregue: %s (event=%s)", url, payload.get("event"))
    else:
        logger.error(
            "Webhook falhou após retries: %s (event=%s)",
            url, payload.get("event"),
        )
