"""Isolamento transacional de uma operação de análise por lead.

Uma falha em um lead não pode invalidar o restante do lote. O savepoint
reverte apenas alterações parciais daquele lead; erros são devolvidos como
resultado estruturado para que o pipeline continue e mantenha o feed honesto.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class LeadProcessingFailure:
    error_type: str
    message: str
    retryable: bool = True


@dataclass(frozen=True)
class GuardedLeadResult(Generic[T]):
    value: Optional[T] = None
    failure: Optional[LeadProcessingFailure] = None

    @property
    def ok(self) -> bool:
        return self.failure is None


async def run_guarded_lead_operation(
    db: Any,
    operation: Callable[[], Awaitable[T]],
    *,
    lead_name: str,
    correlation_id: Optional[str] = None,
) -> GuardedLeadResult[T]:
    """Executa uma operação dentro de savepoint e captura falha por lead.

    O `Session` externo continua utilizável depois da exceção. `flush()` roda
    antes de liberar o savepoint para que violações de persistência também
    sejam isoladas aqui, em vez de explodirem só no commit do lote.
    """
    try:
        with db.begin_nested():
            value = await operation()
            db.flush()
        return GuardedLeadResult(value=value)
    except Exception as exc:  # noqa: BLE001 — fronteira deliberada do lote
        logger.exception(
            "Falha isolada ao processar lead %s correlation_id=%s error_type=%s",
            lead_name,
            correlation_id or "-",
            type(exc).__name__,
        )
        return GuardedLeadResult(
            failure=LeadProcessingFailure(
                error_type=type(exc).__name__,
                message=str(exc)[:500],
                retryable=True,
            )
        )
