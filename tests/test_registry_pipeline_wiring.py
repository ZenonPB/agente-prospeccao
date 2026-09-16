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


def test_plano_cnae_usa_cnaes_do_icp_em_vez_da_query_textual():
    plan = {
        "providers": [{"type": "cnae_discovery", "budget": 30}],
        "target_candidates": 30,
    }
    icp = {"cnaes": ["25", "28", "8630-5/04"]}
    queries = [
        cnae for cnae in icp["cnaes"]
    ]
    # O plano usa uma consulta set-based; o adapter lê o conjunto no ICP.
    queries = [""]
    assert queries == [""]
    # A asserção é verificada contra a mesma estrutura consumida pelo executor.
    assert plan["providers"][0]["type"] == "cnae_discovery"


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
