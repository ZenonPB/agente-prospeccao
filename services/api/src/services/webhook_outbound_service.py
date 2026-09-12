"""Webhook outbound genérico por organização.

A URL configurada é tratada como entrada não confiável. O serviço aceita apenas
HTTPS público, bloqueia credenciais embutidas, hostnames locais e endereços
privados/reservados antes de qualquer conexão. Redirects permanecem desativados.
"""
import asyncio
import ipaddress
import json
import logging
import socket
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import httpx
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from src.db.models import Organization

logger = logging.getLogger(__name__)

RETRY_DELAYS = (0.5, 1.0, 2.0)
TIMEOUT = 5.0

_http_client: Optional["httpx.AsyncClient"] = None


def _ip_is_public(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return bool(ip.is_global)


def _validate_webhook_url(url: str, *, resolved_ips: Optional[list[str]] = None) -> tuple[bool, str]:
    """Valida destino do webhook sem fazer I/O.

    ``resolved_ips`` permite validar o resultado do DNS imediatamente antes da
    conexão. Toda resposta DNS precisa ser global; um único endereço privado faz
    o destino falhar fechado.
    """
    try:
        parsed = urlsplit((url or "").strip())
    except ValueError:
        return False, "URL inválida"

    if parsed.scheme.lower() != "https":
        return False, "Webhook deve usar HTTPS"
    if not parsed.hostname:
        return False, "Webhook sem hostname"
    if parsed.username is not None or parsed.password is not None:
        return False, "Credenciais não são permitidas na URL do webhook"
    if parsed.fragment:
        return False, "Fragmento não é permitido na URL do webhook"

    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        return False, "Hostname local não é permitido"

    # IP literal: valida sem depender de DNS.
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not _ip_is_public(host):
            return False, "Endereço IP não público não é permitido"

    if resolved_ips is not None:
        if not resolved_ips:
            return False, "Hostname sem endereço resolvido"
        if any(not _ip_is_public(ip) for ip in resolved_ips):
            return False, "DNS resolveu para endereço não público"

    return True, "ok"


def _resolve_host_ips(host: str, port: int) -> list[str]:
    """Resolve A/AAAA e devolve somente endereços normalizados, sem conectar."""
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({str(info[4][0]) for info in infos})


async def _destination_is_safe(url: str) -> tuple[bool, str]:
    ok, reason = _validate_webhook_url(url)
    if not ok:
        return ok, reason

    parsed = urlsplit(url)
    try:
        ips = await asyncio.to_thread(
            _resolve_host_ips,
            parsed.hostname or "",
            parsed.port or 443,
        )
    except (OSError, socket.gaierror):
        return False, "Hostname não pôde ser resolvido"
    return _validate_webhook_url(url, resolved_ips=ips)


async def _get_http_client() -> "httpx.AsyncClient":
    """Client singleton com connection pooling e redirects desativados."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=False,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _http_client


def build_webhook_payload(event: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {"event": event, "data": data}


def build_webhook_headers(secret: Optional[str], event: str) -> Dict[str, str]:
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
) -> tuple[bool, Optional[int], str, Optional[str]]:
    """POST com retry; destino é revalidado antes de cada tentativa."""
    body = json.dumps(payload, default=str)
    last_err = None
    last_status = None
    last_body = ""
    client = await _get_http_client()

    for attempt, delay in enumerate((0.0,) + RETRY_DELAYS):
        if delay:
            await asyncio.sleep(delay)

        safe, reason = await _destination_is_safe(url)
        if not safe:
            logger.warning("Webhook bloqueado por política de destino: %s", reason)
            return False, None, "", reason

        try:
            response = await client.post(url, content=body, headers=headers)
            last_status = response.status_code
            last_body = response.text[:500]
            if 200 <= response.status_code < 300:
                return True, last_status, last_body, None
            logger.warning(
                "Webhook respondeu %s na tentativa %d",
                response.status_code,
                attempt + 1,
            )
        except httpx.RequestError as exc:
            last_err = str(exc)
            logger.warning("Webhook falhou na tentativa %d", attempt + 1)
    return False, last_status, last_body, last_err or "Failed after retries"


def enqueue_webhook(
    background_tasks: BackgroundTasks,
    db: Session,
    organization_id: Any,
    event: str,
    data: Dict[str, Any],
) -> bool:
    """Agenda entrega somente quando a configuração básica do destino é segura."""
    if not organization_id:
        return False
    org = (
        db.query(Organization)
        .filter(Organization.id == organization_id)
        .first()
    )
    if not org or not org.webhook_url:
        return False

    url = str(org.webhook_url).strip()
    safe, reason = _validate_webhook_url(url)
    if not safe:
        logger.warning(
            "Webhook da organização %s não foi agendado: %s",
            organization_id,
            reason,
        )
        return False

    payload = build_webhook_payload(event, data)
    headers = build_webhook_headers(org.webhook_secret, event)
    background_tasks.add_task(
        _dispatch_webhook,
        str(organization_id),
        url,
        payload,
        headers,
    )
    return True


async def _dispatch_webhook(
    organization_id: str,
    url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
) -> None:
    """Executa o POST, registra resultado e não expõe segredo em logs."""
    ok, status_code, body_resp, err_msg = await _post_webhook(url, payload, headers)

    try:
        from src.db.session import SessionLocal
        from src.db.models import WebhookLog
        with SessionLocal() as db:
            log_entry = WebhookLog(
                organization_id=organization_id,
                event_type=payload.get("event", "unknown"),
                target_url=url,
                status_code=status_code,
                success=ok,
                payload=payload,
                response_body=body_resp,
                error_message=err_msg if not ok else None,
            )
            db.add(log_entry)
            db.commit()
    except Exception as exc:
        logger.warning("Falha ao salvar WebhookLog no banco: %s", exc)

    if ok:
        logger.info("Webhook entregue (event=%s)", payload.get("event"))
    else:
        logger.error("Webhook falhou após retries (event=%s)", payload.get("event"))
