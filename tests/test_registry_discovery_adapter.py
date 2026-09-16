"""Adapter Registry → DiscoveryExecutor sob o conceito `cnae_discovery`.

RED (TDD): cobre o contrato do adapter — success/empty/disabled/unavailable/
invalid/failed, fallback legado, shadow barato (§13 + ajuste: shadow compara
discovery sem dobrar enrichment/Places/Groq), custo zero e ordem determinística.
"""
from __future__ import annotations


def _adapter(**kwargs):
    from services.registry.discovery_adapter import RegistryCnaeDiscoveryAdapter

    defaults = {"search_service_factory": lambda: None}
    defaults.update(kwargs)
    return RegistryCnaeDiscoveryAdapter(**defaults)


def test_adapter_tem_nome_cnae_discovery_para_reuso_do_conceito():
    adapter = _adapter()
    assert adapter.name == "cnae_discovery"


def test_disabled_sem_registry_configurado():
    import asyncio

    adapter = _adapter(search_service_factory=None)
    result = asyncio.run(adapter.run_with_status("28", {}))
    assert result["status"] == "disabled"
    assert result["items"] == []


def test_invalid_sem_cnae_valido():
    import asyncio

    from services.registry.search import RegistrySearchService

    seen = {}

    class _Svc(RegistrySearchService):
        def __init__(self):
            pass

        def search(self, filters):
            seen["filters"] = filters
            raise AssertionError("não deve consultar sem CNAE")

    adapter = _adapter(search_service_factory=lambda: _Svc())
    result = asyncio.run(adapter.run_with_status("", {}))
    assert result["status"] == "invalid"
    assert result["items"] == []
    assert seen == {}


def test_empty_quando_registry_sem_resultado():
    import asyncio

    from services.registry.search import SearchResult

    class _Svc:
        def search(self, filters):
            return SearchResult(items=[], has_more=False)

    adapter = _adapter(search_service_factory=lambda: _Svc())
    result = asyncio.run(adapter.run_with_status("28", {}))
    assert result["status"] == "empty"
    assert result["items"] == []
    assert result["cost"] == 0


def test_success_converte_candidato_para_dict_do_pipeline():
    import asyncio
    from dataclasses import dataclass

    from services.registry.search import SearchResult

    @dataclass
    class _Cand:
        cnpj: str = "12345678000195"
        razao_social: str = "INDUSTRIA EXEMPLO LTDA"
        nome_fantasia: str = "EXEMPLO"
        cnae_principal: str = "2869100"
        cnae_principal_label: str = "Fabricação de máquinas"
        cnaes_secundarios: list = None
        uf: str = "SP"
        municipio_cod: str = "1234"
        situacao: str = "2"
        matriz: bool = True
        source: str = "receita_cnpj"
        source_snapshot: str = "2026-08"

        def __post_init__(self):
            self.cnaes_secundarios = self.cnaes_secundarios or []

    class _Svc:
        def search(self, filters):
            assert filters.cnae_prefixes == ["28"]
            return SearchResult(items=[_Cand()], has_more=False)

    adapter = _adapter(search_service_factory=lambda: _Svc())
    result = asyncio.run(adapter.run_with_status("28", {}))
    assert result["status"] == "success"
    assert result["cost"] == 0
    (item,) = result["items"]
    assert item["cnpj"] == "12345678000195"
    assert item["provider"] == "cnae_discovery"
    assert item["discovery_source"] == "brazil_company_registry"
    assert item["place_id"].startswith("registry_")


def test_erro_de_conexao_e_indisponibilidade_distinta_de_falha_de_dado():
    import asyncio

    class _Svc:
        def search(self, filters):
            raise ConnectionError("postgres indisponível")

    result = asyncio.run(_adapter(search_service_factory=lambda: _Svc()).run_with_status("28", {}))
    assert result["status"] == "unavailable"


def test_success_preserva_municipio_e_firmographics_sem_geocodificar():
    import asyncio
    from dataclasses import dataclass
    from services.registry.search import SearchResult

    @dataclass
    class _Cand:
        cnpj: str = "12345678000195"
        razao_social: str = "X"
        nome_fantasia: str = "X"
        cnae_principal: str = "2869100"
        cnae_principal_label: str = None
        uf: str = "SP"
        municipio_cod: str = "7107"
        situacao: str = "2"
        matriz: bool = True
        porte: str = "03"
        source_snapshot: str = "2026-08"

    class _Svc:
        def search(self, filters):
            return SearchResult(items=[_Cand()])

    item = asyncio.run(_adapter(search_service_factory=lambda: _Svc()).run("28"))[0]
    assert item["municipio_cod"] == "7107"
    assert item["porte"] == "03"
    assert item["situacao"] == "2"
    assert item["matriz"] is True
    assert item.get("city") is None


def test_failed_em_erro_operacional_nao_vira_empty():
    import asyncio

    class _Svc:
        def search(self, filters):
            raise RuntimeError("banco fora do ar")

    adapter = _adapter(search_service_factory=lambda: _Svc())
    result = asyncio.run(adapter.run_with_status("28", {}))
    assert result["status"] == "failed"
    assert result["items"] == []
    assert result["reason"]


def test_fallback_legado_executa_quando_registry_falha():
    import asyncio

    class _Svc:
        def search(self, filters):
            raise RuntimeError("banco fora do ar")

    async def _legacy(query, ctx):
        return [{"name": "Legado", "provider": "cnae_discovery"}]

    adapter = _adapter(search_service_factory=lambda: _Svc(), legacy_run=_legacy)
    result = asyncio.run(adapter.run_with_status("28", {}))
    assert result["status"] == "fallback"
    assert [i["name"] for i in result["items"]] == ["Legado"]


def test_fallback_legado_recebe_primeiro_cnae_do_icp_quando_query_e_vazia():
    import asyncio

    class _Svc:
        def search(self, filters):
            raise RuntimeError("banco fora do ar")

    seen = []

    async def _legacy(query, ctx):
        seen.append(query)
        return [{"name": "Legado"}]

    adapter = _adapter(search_service_factory=lambda: _Svc(), legacy_run=_legacy)
    result = asyncio.run(adapter.run_with_status("", {"icp": {"cnaes": ["28"]}}))
    assert result["status"] == "fallback"
    assert seen == ["28"]


def test_shadow_compara_sem_promover_nem_duplicar_enrichment():
    import asyncio

    from services.registry.search import SearchResult

    class _Svc:
        def search(self, filters):
            from dataclasses import dataclass

            @dataclass
            class _Cand:
                cnpj: str = "12345678000195"
                razao_social: str = "X"
                nome_fantasia: str = "X"
                cnae_principal: str = "2869100"
                cnae_principal_label: str = None
                cnaes_secundarios: list = None
                uf: str = "SP"
                municipio_cod: str = None
                situacao: str = "2"
                matriz: bool = None
                source: str = "receita_cnpj"
                source_snapshot: str = None

                def __post_init__(self):
                    self.cnaes_secundarios = self.cnaes_secundarios or []

            return SearchResult(items=[_Cand()], has_more=False)

    calls = []

    async def _legacy(query, ctx):
        calls.append(query)
        return [{"cnpj": "12345678000195", "name": "X"}]

    adapter = _adapter(search_service_factory=lambda: _Svc(), legacy_run=_legacy)
    comparison = asyncio.run(adapter.compare("28", {}, target_candidates=10))
    assert comparison["registry_count"] == 1
    assert comparison["legacy_count"] == 1
    assert comparison["overlap"] == 1
    # Shadow compara discovery: legado roda 1x para comparar, sem enrichment.
    assert calls == ["28"]
    assert comparison["enrichment_calls"] == 0
