"""Query-count e economia PG-first (ajuste obrigatório §3 do usuário).

target_candidates=30 NÃO pode materializar dezenas de milhares para fatiar
em Python: o limite desce ao PG como `limit` da query (1 consulta de página),
e o adapter chama o search exatamente 1x por query.
"""
from __future__ import annotations


def test_limit_desce_ao_search_uma_unica_vez():
    import asyncio

    from services.registry.discovery_adapter import RegistryCnaeDiscoveryAdapter
    from services.registry.search import SearchResult

    calls = []

    class _Svc:
        def search(self, filters):
            calls.append(filters)
            return SearchResult(items=[], has_more=False)

    async def _run():
        adapter = RegistryCnaeDiscoveryAdapter(
            search_service_factory=lambda: _Svc(), budget_total=200,
        )
        result = await adapter.run_with_status("28", {"target_candidates": 30})
        assert result["status"] == "empty"

    asyncio.run(_run())
    assert len(calls) == 1
    assert calls[0].limit == 30


def test_targeting_converte_target_em_limit_sem_fatiar():
    from services.registry.targeting import build_search_filters

    filters = build_search_filters({"cnaes": ["28"]}, target_candidates=30)
    assert filters is not None
    assert filters.limit == 30


def test_search_filters_capa_limit_em_100():
    from services.registry.search import SearchFilters

    assert SearchFilters(limit=1000).limit == 100


def test_shadow_limita_queries_e_nao_promove():
    import asyncio

    from services.registry.discovery_adapter import RegistryCnaeDiscoveryAdapter
    from services.registry.search import SearchResult

    search_calls = []

    class _Svc:
        def search(self, filters):
            search_calls.append(filters)
            return SearchResult(items=[], has_more=False)

    legacy_calls = []

    async def _legacy(query, ctx):
        legacy_calls.append(query)
        return []

    async def _run():
        adapter = RegistryCnaeDiscoveryAdapter(
            search_service_factory=lambda: _Svc(), legacy_run=_legacy,
        )
        out = await adapter.compare("28", {}, target_candidates=30)
        assert out["enrichment_calls"] == 0
        assert out["promoted_count"] == 0

    asyncio.run(_run())
    assert len(search_calls) == 1
    assert len(legacy_calls) == 1
