"""Cliente compartilhado para provedores externos (item 5.1 da auditoria).

Concentra num só módulo o que estava espalhado por ~12 serviços:

- `create_http_client` — fábrica de `httpx.AsyncClient` com timeouts e
  verificação de TLS por default (certifi), um único lugar para ajustar
  retry/limites.
- `groq_json_chat` — chamada LLM Groq com schema JSON, log e parse
  centralizados. Consumido por scoring/outreach/template (sem rede duplicada).

Uso em novos serviços:
    from services.provider_client import create_http_client, groq_json_chat
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import certifi
import httpx

from config.settings import settings  # noqa: E402

logger = logging.getLogger(__name__)

# Pacing global por processo: intervalo mínimo entre o INÍCIO de chamadas Groq.
# Evita estourar a janela de TPM/RPM do tier free em batches (scoring em fila).
_groq_lock = asyncio.Lock()
_last_groq_sent = 0.0  # time.monotonic()


async def _pace_groq_start() -> None:
    """Aguarda o intervalo mínimo desde a última chamada Groq (medido no início)."""
    global _last_groq_sent
    interval = getattr(settings, "GROQ_MIN_INTERVAL_SECONDS", 20.0)
    async with _groq_lock:
        now = time.monotonic()
        wait = interval - (now - _last_groq_sent)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_groq_sent = time.monotonic()


def _parse_retry_after(value: Optional[str]) -> Optional[float]:
    """Interpreta o header `Retry-After` (segundos ou HTTP-date)."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        retry_at = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
    except ValueError:
        return None


def create_http_client(timeout: float = 30.0, headers: Optional[Dict[str, str]] = None) -> httpx.AsyncClient:
    """Cria um AsyncClient com defaults seguros: TLS via certifi, follow_redirects."""
    return httpx.AsyncClient(
        verify=certifi.where(),
        follow_redirects=True,
        timeout=timeout,
        headers=headers,
    )


async def groq_json_chat(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    url: str,
    max_tokens: int = 2048,
    temperature: float = 0.2,
    timeout: float = 60.0,
    db=None,
    organization_id: Optional[str] = None,
    quota_key: str = "GROQ_API_KEY",
) -> Optional[Dict[str, Any]]:
    """Chama a Groq pedindo JSON e devolve o dict parseado (ou None em falha).

    - Payload com `response_format: json_object`.
    - Loga erro com HTTP status (sem vazar o corpo inteiro).
    - Aplica backoff simples em 429/5xx (uma retentativa).
    - Item 4.14 (cotas): se `db` + `organization_id` forem informados, verifica
      a cota diária ANTES de chamar (fail-closed: estourada → None) e contabiliza
      uma chamada após cada resposta 200.
    """
    if db is not None and organization_id is not None:
        from services.quota_service import QuotaService
        if not QuotaService.can_consume(db, organization_id, quota_key):
            logger.warning(
                "Cota diária esgotada para %s (org %s) — chamada ao Groq bloqueada.",
                quota_key, organization_id,
            )
            return None

    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    max_attempts = max(1, getattr(settings, "GROQ_MAX_RETRIES", 5))
    retry_base = getattr(settings, "GROQ_RETRY_BASE_SECONDS", 4.0)
    retry_cap = getattr(settings, "GROQ_RETRY_MAX_SECONDS", 60.0)

    attempts = 0
    while True:
        attempts += 1
        await _pace_groq_start()
        try:
            async with create_http_client(timeout=timeout, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }) as client:
                response = await client.post(url, json=payload)
        except httpx.RequestError as e:
            logger.error("Erro de rede ao chamar Groq (%s): %s", model, e)
            return None

        if response.status_code == 200:
            break
        retriable = response.status_code in (429, 500, 502, 503, 504)
        if retriable and attempts < max_attempts:
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            if response.status_code == 429 and retry_after is not None:
                delay = min(retry_after, retry_cap)
            else:
                delay = min(retry_cap, retry_base * (2 ** (attempts - 1)))
            logger.warning(
                "Groq HTTP %s (model=%s) — retry %d/%d em %.1fs",
                response.status_code, model, attempts, max_attempts, delay,
            )
            await asyncio.sleep(delay)
            continue
        logger.error("Groq respondeu HTTP %s (model=%s)", response.status_code, model)
        return None

    if db is not None and organization_id is not None:
        from services.quota_service import QuotaService
        QuotaService.consume(db, organization_id, quota_key)

    try:
        data = response.json()
    except json.JSONDecodeError as e:
        logger.error("Resposta do Groq não é JSON: %s", e)
        return None

    choices = data.get("choices") or []
    if not choices:
        logger.error("Resposta do Groq sem choices (model=%s)", model)
        return None

    content = choices[0].get("message", {}).get("content", "")
    return _parse_json_content(content)


def _parse_json_content(content: Optional[str]) -> Optional[Dict[str, Any]]:
    """Extrai JSON de uma string (remove blocos ```json``` se presentes)."""
    if not content:
        logger.warning("Resposta vazia do Groq.")
        return None
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError as e:
        logger.error("Falha ao decodificar JSON do Groq: %s", e)
        return None


def quota_ok(
    db, organization_id: Optional[str], key_name: str = "GROQ_API_KEY", n: int = 1,
) -> bool:
    """Fail-closed: True se a org ainda tem cota diária para o provedor (4.14).

    Sem `db`/`organization_id` → sem medição (jobs legados/scripts manuais).
    """
    if db is None or organization_id is None:
        return True
    from services.quota_service import QuotaService
    return QuotaService.can_consume(db, organization_id, key_name, n)


def consume_quota(
    db, organization_id: Optional[str], key_name: str = "GROQ_API_KEY", n: int = 1,
) -> None:
    """Contabiliza `n` chamadas da org no provedor hoje (4.14)."""
    if db is None or organization_id is None:
        return
    from services.quota_service import QuotaService
    QuotaService.consume(db, organization_id, key_name, n)
