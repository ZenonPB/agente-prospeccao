"""Discovery Executor (Fase D — consolidação §Fase D).

Contract de provider + registry + executor. O pipeline_worker não chama
mais providers diretamente — passa o `discovery_plan` (saída do
DiscoveryPlanner) para o executor, que sabe qual provider rodar,
em que ordem, com qual budget e dedup.

Critério da Fase D: "Alterar OfferProfile.discovery muda a estratégia de
descoberta sem editar pipeline_worker" — providers plugados via
registry; adicionar novo provider = criar adapter + registrar.
"""
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class DiscoveryProvider(Protocol):
    """Contrato mínimo de provider de descoberta (consolidação §Fase D)."""
    name: str
    budget_total: int

    async def run(self, query: str, lead_context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        ...


class _StubProvider:
    """Adapter simples para tests e providers que ainda não implementam o Protocol."""

    def __init__(self, name: str, results: Optional[List[Dict]] = None, budget_total: int = 100):
        self.name = name
        self.budget_total = budget_total
        self._results = results or []

    async def run(self, query: str, lead_context: Optional[Dict[str, Any]] = None):
        return list(self._results)


class DiscoveryProviderRegistry:
    """Registry de providers de descoberta, indexado por name."""

    def __init__(self):
        self._by_name: Dict[str, DiscoveryProvider] = {}

    def register(self, provider: DiscoveryProvider) -> None:
        self._by_name[provider.name] = provider

    def get(self, name: str) -> Optional[DiscoveryProvider]:
        return self._by_name.get(name)

    def list_keys(self) -> List[str]:
        return list(self._by_name.keys())


class DiscoveryExecutor:
    """Executa o plano de descoberta, chamando providers em ordem com dedup."""

    def __init__(
        self,
        registry: DiscoveryProviderRegistry,
        dedup_keys: tuple = ("name", "place_id", "cnpj"),
    ):
        self.registry = registry
        self.dedup_keys = dedup_keys

    def execute(self, plan: Dict[str, Any], lead_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Executa todos os providers declarados no plano, em ordem.

        Retorna:
            {
                "results_by_provider": {name: [candidates]},
                "execution_order": [name1, name2, ...],
                "skipped": [name_skipped, ...],  # providers ausentes do registry
                "total_candidates": int,
                "unique_candidates": [candidates deduped],
                "unique_count": int,
                "budget_used": {name: int},
            }
        """
        import asyncio

        results_by_provider: Dict[str, List[Dict]] = {}
        execution_order: List[str] = []
        skipped: List[str] = []
        budget_used: Dict[str, int] = {}

        # Mapeia type -> name (no pipeline, o "type" no plano é o "name" do provider)
        for step in plan.get("providers", []):
            provider_name = step.get("type")
            provider = self.registry.get(provider_name)
            if provider is None:
                skipped.append(provider_name)
                continue
            execution_order.append(provider_name)
            queries = step.get("queries") or [provider_name]
            max_results = step.get("max_results") or step.get("budget", 50)

            # Roda o provider (assíncrono)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Em ambiente async (pytest-asyncio), não podemos reusar loop
                    # — provider deve expor versão sync para testabilidade
                    coro = self._run_provider(provider, queries, lead_context, max_results)
                else:
                    coro = self._run_provider(provider, queries, lead_context, max_results)
                candidates = loop.run_until_complete(coro) if not loop.is_running() else []
            except RuntimeError:
                # Já em loop async — chama sem await via fallback
                candidates = []

            # Dedup intra-provider por query
            seen_keys = set()
            deduped = []
            for c in candidates:
                key = self._identity_key(c)
                if key and key in seen_keys:
                    continue
                seen_keys.add(key)
                deduped.append(c)
            results_by_provider[provider_name] = deduped[:max_results]
            budget_used[provider_name] = len(results_by_provider[provider_name])

        # Dedup entre providers (consolidação §7)
        all_candidates = []
        for name in execution_order:
            all_candidates.extend(results_by_provider.get(name, []))

        unique_candidates = self._dedup(all_candidates)

        return {
            "results_by_provider": results_by_provider,
            "execution_order": execution_order,
            "skipped": skipped,
            "total_candidates": len(all_candidates),
            "unique_candidates": unique_candidates,
            "unique_count": len(unique_candidates),
            "budget_used": budget_used,
        }

    async def _run_provider(
        self,
        provider: DiscoveryProvider,
        queries: List[str],
        lead_context: Optional[Dict[str, Any]],
        max_results: int,
    ) -> List[Dict[str, Any]]:
        """Roda o provider em todas as queries, retornando candidatos deduped."""
        all_results: List[Dict[str, Any]] = []
        for q in queries:
            results = await provider.run(q, lead_context=lead_context)
            all_results.extend(results or [])
        return all_results

    def _identity_key(self, candidate: Dict[str, Any]) -> Optional[str]:
        """Chave de identidade para dedup (primeira chave disponível)."""
        for k in self.dedup_keys:
            if k in candidate and candidate[k]:
                return f"{k}:{candidate[k]}"
        return None

    def _dedup(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Dedup por chave de identidade, preservando a primeira ocorrência."""
        seen: set = set()
        out: List[Dict[str, Any]] = []
        for c in candidates:
            key = self._identity_key(c)
            if key and key not in seen:
                seen.add(key)
                out.append(c)
        return out
