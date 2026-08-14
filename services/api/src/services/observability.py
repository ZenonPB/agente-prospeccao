"""Logs estruturados de eventos de negócio.

Os eventos de cadência/abertura/opt-out são emitidos aqui num formato estável
`event=<name> key=value ...` em uma linha única, permitindo grep e ingestão em
ferramentas de observabilidade sem depender de um JSON formatter global.
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger("prospeccao.events")


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
    payload.update(fields)

    rendered = " ".join(
        f"{k}={v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)}"
        for k, v in payload.items()
    )
    logger.info(rendered)
