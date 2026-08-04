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
import json
import logging
from typing import Any, Dict, List, Optional

import certifi
import httpx

logger = logging.getLogger(__name__)


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
) -> Optional[Dict[str, Any]]:
    """Chama a Groq pedindo JSON e devolve o dict parseado (ou None em falha).

    - Payload com `response_format: json_object`.
    - Loga erro com HTTP status (sem vazar o corpo inteiro).
    - Aplica backoff simples em 429/5xx (uma retentativa).
    """
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

    attempts = 0
    while True:
        attempts += 1
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
        if response.status_code in (429, 500, 502, 503, 504) and attempts < 2:
            import asyncio
            await asyncio.sleep(1.5 * attempts)
            continue
        logger.error("Groq respondeu HTTP %s (model=%s)", response.status_code, model)
        return None

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
