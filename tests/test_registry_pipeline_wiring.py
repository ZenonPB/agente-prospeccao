"""Wiring 1C no pipeline: default seguro, Registry opt-in e shadow barato.

Trava regressão do runtime produtivo (OfferProfile → plano →
DiscoveryProviderRegistry → DiscoveryExecutor):
- flag desligada → adapter legado (comportamento idêntico ao anterior);
- flag ligada → RegistryCnaeDiscoveryAdapter com fallback legado;
- shadow desligado/ausente → no-op sem tocar o banco;
- shadow é coroutine (nunca loop aninhado dentro do job async).
"""
from __future__ import annotations

import asyncio
import inspect


def _worker():
    import src.pipeline_worker as worker

    return worker


def test_shadow_e_coroutine_sem_loop_aninhado():
    worker = _worker()

    assert inspect.iscoroutinefunction(worker._persist_registry_shadow_comparison)


def test_flag_desligada_mantem_adapter_legado(monkeypatch):
    worker = _worker()
    monkeypatch.setattr(worker.settings, "REGISTRY_DISCOVERY_ENABLED", False)

    adapter = worker._build_cnae_discovery_adapter(object(), 50)
    assert type(adapter).__name__ == "CnaeDiscoveryAdapter"
    assert adapter.name == "cnae_discovery"


def test_flag_ligada_usa_registry_com_fallback_legado(monkeypatch):
    worker = _worker()
    monkeypatch.setattr(worker.settings, "REGISTRY_DISCOVERY_ENABLED", True)

    adapter = worker._build_cnae_discovery_adapter(object(), 50)
    assert type(adapter).__name__ == "RegistryCnaeDiscoveryAdapter"
    assert adapter.name == "cnae_discovery"
    assert adapter._legacy_run is not None


def test_plano_cnae_usa_cnaes_do_icp_em_vez_da_query_textual(monkeypatch):
    """O wiring real entrega o ICP ao Registry sem apagar a query legada."""
    import asyncio

    import src.pipeline_worker as worker
    from services.registry.search import SearchResult

    seen = []

    class _RegistryService:
        def search(self, filters):
            seen.append(filters)
            return SearchResult()

    class _LegacyService:
        async def search_by_cnae(self, **kwargs):
            raise AssertionError("não deve rodar no caminho Registry feliz")

    from services.registry.discovery_adapter import RegistryCnaeDiscoveryAdapter

    monkeypatch.setattr(worker.settings, "REGISTRY_DISCOVERY_ENABLED", True)
    monkeypatch.setattr(worker, "CnaeDiscoveryService", lambda: _LegacyService())
    monkeypatch.setattr(
        worker,
        "_build_cnae_discovery_adapter",
        lambda db, max_leads: RegistryCnaeDiscoveryAdapter(
            search_service_factory=lambda: _RegistryService(), budget_total=max_leads
        ),
    )
    result = asyncio.run(worker._collect_cnae_discovery(
        object(), icp={"cnaes": ["25", "28", "8630-5/04"]}, max_leads=30,
    ))
    assert result == []
    assert len(seen) == 1
    assert seen[0].cnae_prefixes == ["25", "28"]
    assert seen[0].cnaes == ["8630504"]


def test_queries_do_runtime_preservam_legado_e_registry_set_based(monkeypatch):
    worker = _worker()

    assert worker._discovery_queries_for_step(
        "cnae_discovery",
        search_queries=["metalúrgica", "usinagem"],
        legacy_cnae_query="28",
        registry_enabled=False,
        has_declarative_cnae=True,
    ) == ["metalúrgica", "usinagem"]
    assert worker._discovery_queries_for_step(
        "cnae_discovery",
        search_queries=["metalúrgica"],
        legacy_cnae_query="28",
        registry_enabled=True,
        has_declarative_cnae=True,
    ) == [""]
    assert worker._discovery_queries_for_step(
        "cnae_discovery",
        search_queries=["metalúrgica"],
        legacy_cnae_query="metalúrgica",
        registry_enabled=True,
        has_declarative_cnae=False,
    ) == ["metalúrgica"]


def test_registry_off_entrega_cnae_legado_ao_servico_real(monkeypatch):
    import asyncio
    import src.pipeline_worker as worker

    calls = []

    class _LegacyService:
        async def search_by_cnae(self, **kwargs):
            calls.append(kwargs)
            return [{"name": "Legado"}]

    monkeypatch.setattr(worker.settings, "REGISTRY_DISCOVERY_ENABLED", False)
    monkeypatch.setattr(worker, "CnaeDiscoveryService", lambda: _LegacyService())
    result = asyncio.run(worker._collect_cnae_discovery(
        object(), cnae_code="28", max_leads=7,
    ))
    assert result == [{"name": "Legado"}]
    assert calls[0]["cnae_code"] == "28"


def test_registry_fallback_entrega_cnae_valido_ao_legado(monkeypatch):
    import asyncio
    import src.pipeline_worker as worker
    from services.registry.discovery_adapter import RegistryCnaeDiscoveryAdapter

    seen = []

    class _RegistryService:
        def search(self, filters):
            raise RuntimeError("registry indisponível")

    class _LegacyService:
        async def search_by_cnae(self, **kwargs):
            seen.append(kwargs)
            return [{"name": "Legado"}]

    monkeypatch.setattr(worker.settings, "REGISTRY_DISCOVERY_ENABLED", True)
    monkeypatch.setattr(worker, "CnaeDiscoveryService", lambda: _LegacyService())
    monkeypatch.setattr(
        worker,
        "_build_cnae_discovery_adapter",
        lambda db, max_leads: RegistryCnaeDiscoveryAdapter(
            search_service_factory=lambda: _RegistryService(), budget_total=max_leads,
            legacy_run=lambda query, ctx: worker.CnaeDiscoveryAdapter(
                _LegacyService(), budget_total=max_leads
            ).run(query, ctx),
        ),
    )
    result = asyncio.run(worker._collect_cnae_discovery(
        object(), icp={"cnaes": ["28"]}, max_leads=7,
    ))
    assert result == [{"name": "Legado"}]
    assert seen[0]["cnae_code"] == "28"


def test_registry_fallback_prioriza_cnae_code_explicito(monkeypatch):
    import asyncio
    import src.pipeline_worker as worker
    from services.registry.discovery_adapter import RegistryCnaeDiscoveryAdapter

    seen = []

    class _RegistryService:
        def search(self, filters):
            raise RuntimeError("registry indisponível")

    class _LegacyService:
        async def search_by_cnae(self, **kwargs):
            seen.append(kwargs)
            return [{"name": "Legado"}]

    monkeypatch.setattr(worker.settings, "REGISTRY_DISCOVERY_ENABLED", True)
    monkeypatch.setattr(
        worker,
        "_build_cnae_discovery_adapter",
        lambda db, max_leads: RegistryCnaeDiscoveryAdapter(
            search_service_factory=lambda: _RegistryService(), budget_total=max_leads,
            legacy_run=lambda query, ctx: worker.CnaeDiscoveryAdapter(
                _LegacyService(), budget_total=max_leads
            ).run(query, ctx),
        ),
    )
    result = asyncio.run(worker._collect_cnae_discovery(
        object(), cnae_code="250", icp={}, max_leads=7,
    ))
    assert result == [{"name": "Legado"}]
    assert seen[0]["cnae_code"] == "250"


def test_adapter_registry_consume_icp_sem_segmento_textual():
    import asyncio
    from services.registry.discovery_adapter import RegistryCnaeDiscoveryAdapter
    from services.registry.search import SearchResult

    seen = []

    class _Svc:
        def search(self, filters):
            seen.append(filters)
            return SearchResult()

    async def _run():
        adapter = RegistryCnaeDiscoveryAdapter(search_service_factory=lambda: _Svc())
        return await adapter.run_with_status("", {
            "icp": {"cnaes": ["28"], "segments": ["indústria metalúrgica"]},
            "target_candidates": 30,
        })

    result = asyncio.run(_run())
    assert result["status"] == "empty"
    assert seen[0].cnae_prefixes == ["28"]


def test_shadow_desligado_e_noop_sem_banco(monkeypatch):
    worker = _worker()
    monkeypatch.setattr(worker.settings, "REGISTRY_SHADOW_MODE", False)
    monkeypatch.setattr(worker.settings, "REGISTRY_DISCOVERY_ENABLED", True)

    class _Db:
        def __getattr__(self, name):
            raise AssertionError("shadow desligado não deve tocar o banco")

    result = asyncio.run(
        worker._persist_registry_shadow_comparison(
            _Db(), organization_id="org-a", execution_plan={"providers": []},
        )
    )
    assert result is None


def test_shadow_sem_step_cnae_e_noop(monkeypatch):
    worker = _worker()
    monkeypatch.setattr(worker.settings, "REGISTRY_SHADOW_MODE", True)
    monkeypatch.setattr(worker.settings, "REGISTRY_DISCOVERY_ENABLED", True)

    result = asyncio.run(
        worker._persist_registry_shadow_comparison(
            object(), organization_id="org-a",
            execution_plan={"providers": [{"type": "google_places"}]},
        )
    )
    assert result is None
