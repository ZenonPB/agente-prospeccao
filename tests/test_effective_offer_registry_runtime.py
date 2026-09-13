"""Invariantes do OfferProfileRegistry efetivo no runtime do pipeline."""
from __future__ import annotations

import asyncio

from services.prospecting.default_profiles import get_base_registry, get_default_registry
from services.prospecting.effective_offer_registry import build_effective_registry
from services.prospecting.offer_profile import OfferProfileRegistry
from services.prospecting.runtime_offer_registry import use_runtime_offer_registry


class _EmptyQuery:
    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return []


class _EmptyDB:
    def query(self, *args, **kwargs):
        return _EmptyQuery()


def test_default_registry_fora_do_contexto_e_catalogo_base():
    assert get_default_registry() is get_base_registry()
    assert get_default_registry().get("landing_page") is not None


def test_runtime_registry_e_restaurado_ao_sair_do_contexto():
    base = get_base_registry()
    custom = OfferProfileRegistry()

    with use_runtime_offer_registry(custom):
        assert get_default_registry() is custom

    assert get_default_registry() is base


def test_contexto_aninhado_restaura_o_registry_externo():
    outer = OfferProfileRegistry()
    inner = OfferProfileRegistry()

    with use_runtime_offer_registry(outer):
        assert get_default_registry() is outer
        with use_runtime_offer_registry(inner):
            assert get_default_registry() is inner
        assert get_default_registry() is outer


async def _observe_registry(registry: OfferProfileRegistry):
    with use_runtime_offer_registry(registry):
        before = get_default_registry()
        await asyncio.sleep(0)
        after = get_default_registry()
        return before, after


def test_contextvar_isola_jobs_concorrentes():
    first = OfferProfileRegistry()
    second = OfferProfileRegistry()

    async def scenario():
        return await asyncio.gather(
            _observe_registry(first),
            _observe_registry(second),
        )

    (first_before, first_after), (second_before, second_after) = asyncio.run(scenario())
    assert first_before is first_after is first
    assert second_before is second_after is second
    assert first_before is not second_before


def test_build_effective_registry_sempre_parte_do_catalogo_base():
    """Overlay do workspace corrente não pode contaminar outro workspace."""
    runtime_only = OfferProfileRegistry()

    with use_runtime_offer_registry(runtime_only):
        assert get_default_registry() is runtime_only
        effective = build_effective_registry(_EmptyDB(), "workspace-b")

    assert effective is not runtime_only
    assert effective.get("landing_page") is not None
    assert effective.get("mechanical_project") is not None
