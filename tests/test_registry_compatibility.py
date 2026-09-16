"""Compatibilidade 1C/1D: tudo que funcionava continua funcionando.

Registry desligado → adapter legado idêntico; Registry vazio → empty;
campanha antiga sem CNAE → None (providers existentes); Places intacto;
web intel desligada por default (serviço opt-in, sem auto-execução).
"""
from __future__ import annotations


def test_registry_desligado_monta_adapter_legado():
    from services.prospecting.discovery_providers import CnaeDiscoveryAdapter
    from src.pipeline_worker import _build_cnae_discovery_adapter

    adapter = _build_cnae_discovery_adapter(db=None, max_leads=50)
    assert isinstance(adapter, CnaeDiscoveryAdapter)
    assert adapter.name == "cnae_discovery"


def test_campanha_antiga_sem_cnae_nao_ativa_registry():
    from services.registry.targeting import build_search_filters

    assert build_search_filters({}) is None
    assert build_search_filters({"segments": ["industria"]}) is None


def test_places_adapter_intacto():
    from services.prospecting.discovery_providers import GooglePlacesAdapter

    adapter = GooglePlacesAdapter(places_service=None, budget_total=100)
    assert adapter.name == "google_places"


def test_executor_aceita_adapter_registry_como_cnae_discovery():
    from services.prospecting.discovery_executor import (
        DiscoveryProviderRegistry, _StubProvider,
    )

    registry = DiscoveryProviderRegistry()
    registry.register(_StubProvider("cnae_discovery", results=[{"name": "R"}]))
    registry.register(_StubProvider("google_places", results=[{"name": "P"}]))
    assert set(registry.list_keys()) == {"cnae_discovery", "google_places"}


def test_web_intel_e_opt_in_sem_auto_execucao_no_pipeline():
    import inspect

    import src.pipeline_worker as pw

    source = inspect.getsource(pw)
    assert "PublicWebIntelligence" not in source
    assert "web_intelligence" not in source


def test_coleta_cnae_sem_targeting_registry_preserva_legado(monkeypatch):
    import asyncio
    import src.pipeline_worker as worker

    monkeypatch.setattr(worker.settings, "REGISTRY_DISCOVERY_ENABLED", True)
    calls = []

    class _Legacy:
        async def search_by_cnae(self, **kwargs):
            calls.append(kwargs)
            return [{"name": "Legado"}]

    monkeypatch.setattr(worker, "CnaeDiscoveryService", lambda: _Legacy())
    result = asyncio.run(worker._collect_cnae_discovery(object(), max_leads=3))
    assert result == [{"name": "Legado"}]
    assert calls and calls[0]["limit"] == 3


def test_coleta_cnae_com_cnpjs_preserva_contrato_legado(monkeypatch):
    import asyncio
    import src.pipeline_worker as worker

    monkeypatch.setattr(worker.settings, "REGISTRY_DISCOVERY_ENABLED", True)
    calls = []

    class _Legacy:
        async def search_by_cnae(self, **kwargs):
            calls.append(kwargs)
            return []

    monkeypatch.setattr(worker, "CnaeDiscoveryService", lambda: _Legacy())
    asyncio.run(worker._collect_cnae_discovery(
        object(), cnae_code="28", cnpjs=["12345678000195"], max_leads=3,
    ))
    assert calls[0]["cnpjs_input"] == ["12345678000195"]
