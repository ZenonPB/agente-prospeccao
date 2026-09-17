"""Isolamento transacional de uma operação de análise por lead.

Uma falha em um lead não pode invalidar o restante do lote. Em modo legado, o
savepoint reverte apenas alterações parciais daquele lead; erros são devolvidos
como resultado estruturado para que o pipeline continue e mantenha o feed
honesto.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar

from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm.exc import DetachedInstanceError

logger = logging.getLogger(__name__)

T = TypeVar("T")

#: Erros de sessão/dados que nunca se resolvem repetindo: re-fila só mascara
#: o problema. Qualquer outro erro continua repetível (ex.: rate-limit da IA).
_NON_RETRYABLE_ERRORS = (InvalidRequestError, DetachedInstanceError)


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


def _retryable(exc: BaseException) -> bool:
    """Erro de sessão/dado não se resolve repetindo; o resto, sim."""
    return not isinstance(exc, _NON_RETRYABLE_ERRORS)


async def run_guarded_lead_operation(
    db: Any,
    operation: Callable[[], Awaitable[T]],
    *,
    lead_name: str,
    correlation_id: Optional[str] = None,
    isolated: bool = False,
    session_factory: Any = None,
) -> GuardedLeadResult[T]:
    """Executa uma operação com falha isolada por lead.

    Modo legado (`isolated=False`): savepoint na sessão dada; `operation` não
    recebe argumentos. `flush()` roda antes de liberar o savepoint para que
    violações de persistência também sejam isoladas aqui, em vez de explodirem
    só no commit do lote.

    Modo isolado (`isolated=True`): abre sessão dedicada via
    `session_factory`, entrega à operação (`operation(op_db)`), commita no
    sucesso e reverte+fecha sempre. Sem savepoint: commits no meio da operação
    (ex.: contabilidade de cota após Groq 200) não invalidam a sessão nem os
    toques seguintes — era o `InvalidRequestError` que derrubava 100% dos
    leads. O chamador não deve reutilizar nada da sessão dedicada depois
    (para ler o resultado, recarregue na sessão própria); a sessão do lote
    nunca é tocada aqui e continua utilizável.

    O `Session` externo continua utilizável depois da exceção (modo legado) e
    a sessão dedicada é sempre fechada (modo isolado).
    """
    if isolated:
        if session_factory is None:
            raise ValueError("isolated=True exige session_factory")
        op_db = session_factory()
        try:
            value = await operation(op_db)
            op_db.commit()
            return GuardedLeadResult(value=value)
        except Exception as exc:  # noqa: BLE001 — fronteira deliberada do lote
            op_db.rollback()
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
                    retryable=_retryable(exc),
                )
            )
        finally:
            op_db.close()
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
                retryable=_retryable(exc),
            )
        )
