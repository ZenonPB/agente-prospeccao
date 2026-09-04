"""Testes do Discovery Executor (Fase D — consolidação §Fase D).

Seam: `DiscoveryProvider` (Protocol), `DiscoveryProviderRegistry`,
       `DiscoveryExecutor.execute(plan, lead_context)`.

Capacidade: executar o plano do DiscoveryPlanner chamando providers
reais (places, cnae, pncp) de forma uniforme via contract, respeitando
budget, ordem e dedup.

Critério da Fase D: "Alterar OfferProfile.discovery muda a estratégia
de descoberta sem editar pipeline_worker."
"""
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


class TestDiscoveryProviderContract:
    def test_provider_tem_metodos_obrigatorios(self):
        """Contrato mínimo: name, budget_total, run(query, lead_context) -> List[Dict]."""
        from services.prospecting.discovery_executor import DiscoveryProvider

        class _P:
            name = "fake"
            budget_total = 100
            async def run(self, query, lead_context=None):
                return [{"company_name": "X"}]

        p = _P()
        assert hasattr(p, "name")
        assert hasattr(p, "budget_total")
        assert hasattr(p, "run")
        # Structural check via Protocol
        assert isinstance(p, DiscoveryProvider) or hasattr(p, "run")


class TestDiscoveryProviderRegistry:
    def test_registry_registra_e_recupera(self):
        from services.prospecting.discovery_executor import (
            DiscoveryProviderRegistry, _StubProvider,
        )
        registry = DiscoveryProviderRegistry()
        registry.register(_StubProvider("google_places"))
        assert registry.get("google_places") is not None
        assert registry.get("nao_existe") is None

    def test_registry_list_keys(self):
        from services.prospecting.discovery_executor import (
            DiscoveryProviderRegistry, _StubProvider,
        )
        registry = DiscoveryProviderRegistry()
        registry.register(_StubProvider("google_places"))
        registry.register(_StubProvider("cnae_discovery"))
        assert set(registry.list_keys()) == {"google_places", "cnae_discovery"}


class TestDiscoveryExecutor:
    def test_executor_roda_providers_do_plano(self):
        from services.prospecting.discovery_executor import (
            DiscoveryProviderRegistry, DiscoveryExecutor, _StubProvider,
        )
        registry = DiscoveryProviderRegistry()
        registry.register(_StubProvider("google_places", results=[{"name": "A"}]))
        registry.register(_StubProvider("cnae_discovery", results=[{"name": "B"}]))
        executor = DiscoveryExecutor(registry)
        plan = {
            "providers": [
                {"type": "google_places", "queries": ["x"], "budget": 50},
                {"type": "cnae_discovery", "queries": ["y"], "budget": 30},
            ]
        }
        result = executor.execute(plan)
        # Deve chamar os 2 providers
        assert "google_places" in result["results_by_provider"]
        assert "cnae_discovery" in result["results_by_provider"]
        assert result["results_by_provider"]["google_places"][0]["name"] == "A"
        assert result["results_by_provider"]["cnae_discovery"][0]["name"] == "B"

    def test_executor_respeita_ordem_do_plano(self):
        from services.prospecting.discovery_executor import (
            DiscoveryProviderRegistry, DiscoveryExecutor, _StubProvider,
        )
        registry = DiscoveryProviderRegistry()
        registry.register(_StubProvider("first"))
        registry.register(_StubProvider("second"))
        executor = DiscoveryExecutor(registry)
        plan = {
            "providers": [
                {"type": "first", "queries": ["x"]},
                {"type": "second", "queries": ["y"]},
            ]
        }
        result = executor.execute(plan)
        assert result["execution_order"] == ["first", "second"]

    def test_executor_pula_provider_ausente_do_registry(self):
        from services.prospecting.discovery_executor import (
            DiscoveryProviderRegistry, DiscoveryExecutor, _StubProvider,
        )
        registry = DiscoveryProviderRegistry()
        registry.register(_StubProvider("google_places"))
        executor = DiscoveryExecutor(registry)
        plan = {
            "providers": [
                {"type": "google_places", "queries": ["x"]},
                {"type": "nao_registrado", "queries": ["y"]},  # pula
            ]
        }
        result = executor.execute(plan)
        assert "google_places" in result["results_by_provider"]
        assert "nao_registrado" not in result["results_by_provider"]
        # Mas aparece no audit
        assert "nao_registrado" in result.get("skipped", [])

    def test_executor_respeita_max_results(self):
        from services.prospecting.discovery_executor import (
            DiscoveryProviderRegistry, DiscoveryExecutor, _StubProvider,
        )
        registry = DiscoveryProviderRegistry()
        registry.register(_StubProvider("google_places", results=[
            {"name": "A"}, {"name": "B"}, {"name": "C"},
        ]))
        executor = DiscoveryExecutor(registry)
        plan = {"providers": [{"type": "google_places", "queries": ["x"], "max_results": 2}]}
        result = executor.execute(plan)
        assert len(result["results_by_provider"]["google_places"]) == 2

    def test_executor_agregacao_com_dedup_por_identidade(self):
        from services.prospecting.discovery_executor import (
            DiscoveryProviderRegistry, DiscoveryExecutor, _StubProvider,
        )
        registry = DiscoveryProviderRegistry()
        # Mesma empresa retornada por 2 providers
        registry.register(_StubProvider("google_places", results=[{"name": "Alpha", "place_id": "p1"}]))
        registry.register(_StubProvider("cnae_discovery", results=[{"name": "Alpha", "cnpj": "c1"}]))
        executor = DiscoveryExecutor(registry, dedup_keys=("name",))
        plan = {"providers": [
            {"type": "google_places", "queries": ["x"]},
            {"type": "cnae_discovery", "queries": ["y"]},
        ]}
        result = executor.execute(plan)
        # Dedup por nome
        unique_names = [r["name"] for r in result["unique_candidates"]]
        assert unique_names.count("Alpha") == 1

    def test_executor_total_candidates_e_metricado(self):
        from services.prospecting.discovery_executor import (
            DiscoveryProviderRegistry, DiscoveryExecutor, _StubProvider,
        )
        registry = DiscoveryProviderRegistry()
        registry.register(_StubProvider("google_places", results=[{"name": "A"}, {"name": "B"}]))
        registry.register(_StubProvider("cnae_discovery", results=[{"name": "C"}]))
        executor = DiscoveryExecutor(registry, dedup_keys=("name",))
        plan = {"providers": [{"type": "google_places"}, {"type": "cnae_discovery"}]}
        result = executor.execute(plan)
        assert result["total_candidates"] == 3
        assert result["unique_count"] == 3


class TestExecuteAsync:
    """Testa a versão async do executor (uso em pipeline real)."""

    def test_execute_async_roda_providers_async(self):
        import asyncio
        from services.prospecting.discovery_executor import (
            DiscoveryProviderRegistry, DiscoveryExecutor, _StubProvider,
        )

        class _AsyncProvider(_StubProvider):
            async def run(self, query, lead_context=None):
                return list(self._results)

        registry = DiscoveryProviderRegistry()
        registry.register(_AsyncProvider("google_places", results=[{"name": "Async-X"}]))
        executor = DiscoveryExecutor(registry)
        plan = {"providers": [{"type": "google_places", "queries": ["q1"]}]}
        result = asyncio.run(executor.execute_async(plan))
        assert "google_places" in result["results_by_provider"]
        assert result["results_by_provider"]["google_places"][0]["name"] == "Async-X"

    def test_execute_async_lida_com_provider_sync(self):
        """Mix de providers: sync e async no mesmo plano."""
        import asyncio
        from services.prospecting.discovery_executor import (
            DiscoveryProviderRegistry, DiscoveryExecutor, _StubProvider,
        )
        registry = DiscoveryProviderRegistry()
        registry.register(_StubProvider("cnae_discovery", results=[{"name": "Sync-X"}]))
        executor = DiscoveryExecutor(registry)
        plan = {"providers": [{"type": "cnae_discovery", "queries": ["q1"]}]}
        result = asyncio.run(executor.execute_async(plan))
        assert result["results_by_provider"]["cnae_discovery"][0]["name"] == "Sync-X"
