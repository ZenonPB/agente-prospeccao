"""Correlacao de requests HTTP fim-a-fim.

Toda request recebe (ou reaproveita) um identificador estavel de correlacao,
guardado num ``ContextVar`` acessivel por qualquer camada sincrona ou async
dentro do ciclo da request. Isso liga o log de acesso a request -> job ->
provider trace (ver ``provider_execution_metrics.correlation_id`` e
``/api/analytics/provider-trace/{correlation_id}``) sem propagar o id
manualmente em cada chamada.

Contrato publico:
- header aceito na entrada: ``X-Request-ID`` ou ``X-Correlation-ID``;
- header devolvido na resposta: ``X-Request-ID``;
- ``get_request_id()`` devolve o id da request corrente ou ``None`` fora dela;
- ids invalidos/ausentes sao substituidos por um UUID4 novo.
"""
from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

# Nome do header canonico (entrada e saida) e alias aceito na entrada.
REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"

# Limite defensivo: ids externos muito longos nao sao propagados (evita log
# injection / abuso). Ids validos costumam ser UUIDs (36 chars).
_MAX_ID_LENGTH = 128

_request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def new_request_id() -> str:
    """Gera um identificador de correlacao novo."""
    return str(uuid.uuid4())


def get_request_id() -> Optional[str]:
    """Devolve o id de correlacao da request corrente (ou ``None``)."""
    return _request_id_var.get()


def set_request_id(value: Optional[str]):
    """Define o id de correlacao corrente; devolve o token para reset.

    Uso tipico e o middleware; util tambem em testes e workers que queiram
    correlacionar um bloco de trabalho.
    """
    return _request_id_var.set(value)


def reset_request_id(token) -> None:
    """Restaura o valor anterior do ``ContextVar`` (evita vazamento entre requests)."""
    _request_id_var.reset(token)


def _sanitize(candidate: Optional[str]) -> Optional[str]:
    """Aceita apenas ids nao vazios e dentro do limite; caso contrario ``None``."""
    if not candidate:
        return None
    trimmed = candidate.strip()
    if not trimmed or len(trimmed) > _MAX_ID_LENGTH:
        return None
    return trimmed


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Atribui/propaga o id de correlacao por request.

    Registrado como middleware mais externo para cobrir todo o ciclo, inclusive
    respostas de erro. O ``ContextVar`` e sempre restaurado no ``finally``.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        incoming = _sanitize(
            request.headers.get(REQUEST_ID_HEADER)
            or request.headers.get(CORRELATION_ID_HEADER)
        )
        request_id = incoming or new_request_id()
        token = set_request_id(request_id)
        # Disponivel tambem em request.state para handlers que preferem ler dali.
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
