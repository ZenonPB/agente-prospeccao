"""Logs estruturados de eventos de negócio.

Os eventos de cadência/abertura/opt-out são emitidos aqui num formato estável
`event=<name> key=value ...` em uma linha única, permitindo grep e ingestão em
ferramentas de observabilidade sem depender de um JSON formatter global.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("prospeccao.events")

_SENSITIVE_FIELD_PARTS = (
    "authorization",
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
)


def _safe_value(key: str, value: Any) -> Any:
    """Remove credenciais de campos livres antes de escrever no log."""
    normalized_key = key.lower().replace("-", "_")
    if any(part in normalized_key for part in _SENSITIVE_FIELD_PARTS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _safe_value(str(k), v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_value(key, item) for item in value]
    return value


def log_event(
    event: str,
    *,
    lead_id: Optional[str] = None,
    organization_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **fields: Any,
) -> None:
    """Emite um log estruturado no formato `event=<event> <k>=<v> ...`.

    `event` e `lead_id`/`organization_id` são sempre incluídos (filtro comum);
    demais campos passam como pares chave=valor. Valores não-simples (dicts)
    são serializados como JSON compacto.
    """
    payload: dict[str, Any] = {"event": event}
    if lead_id:
        payload["lead_id"] = lead_id
    if organization_id:
        payload["organization_id"] = organization_id
    if user_id:
        payload["user_id"] = user_id
    payload.update({key: _safe_value(key, value) for key, value in fields.items()})

    rendered = " ".join(
        f"{k}={v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)}"
        for k, v in payload.items()
    )
    logger.info(rendered)


def log_job_event(
    event: str,
    *,
    job_id: str,
    organization_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    started_at: Optional[datetime] = None,
    error: Optional[str] = None,
    **fields: Any,
) -> None:
    """Registra o ciclo de um job com correlação e duração auditáveis."""
    duration_ms = None
    if started_at:
        start = started_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        duration_ms = max(0, int((datetime.now(timezone.utc) - start).total_seconds() * 1000))
    log_event(
        event,
        job_id=job_id,
        organization_id=organization_id,
        campaign_id=campaign_id,
        lead_id=lead_id,
        duration_ms=duration_ms,
        error=error,
        **fields,
    )
