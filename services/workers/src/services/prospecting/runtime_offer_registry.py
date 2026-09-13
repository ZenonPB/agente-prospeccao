"""Contexto de runtime para OfferProfileRegistry por workspace.

O pipeline roda em tarefas assíncronas. Um ``ContextVar`` mantém o registry
já resolvido para a organização do job sem usar estado global mutável e sem
vazar configurações entre jobs concorrentes.

Módulos legados que ainda chamam ``get_default_registry()`` passam a enxergar
o registry efetivo enquanto estiverem dentro deste contexto; fora dele o
comportamento continua sendo o catálogo base imutável.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator

from services.prospecting.offer_profile import OfferProfileRegistry


_runtime_registry: ContextVar[OfferProfileRegistry | None] = ContextVar(
    "runtime_offer_profile_registry",
    default=None,
)


def get_runtime_offer_registry() -> OfferProfileRegistry | None:
    """Retorna o registry efetivo ligado à tarefa atual, quando existir."""
    return _runtime_registry.get()


@contextmanager
def use_runtime_offer_registry(
    registry: OfferProfileRegistry,
) -> Iterator[OfferProfileRegistry]:
    """Liga ``registry`` apenas ao contexto/tarefa atual e restaura ao sair."""
    token: Token[OfferProfileRegistry | None] = _runtime_registry.set(registry)
    try:
        yield registry
    finally:
        _runtime_registry.reset(token)
