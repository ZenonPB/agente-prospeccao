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
        results_by_provider: Dict[str, List[Dict]] = {}
        execution_order: List[str] = []
        skipped: List[str] = []
        budget_used: Dict[str, int] = {}
        total_budget = plan.get("max_results") or plan.get("target_candidates")
        remaining_budget = int(total_budget) if total_budget is not None else None

        for step in plan.get("providers", []):
            if remaining_budget is not None and remaining_budget <= 0:
                skipped.append(step.get("type"))
                continue
            provider_name = step.get("type")
            provider = self.registry.get(provider_name)
            if provider is None:
                skipped.append(provider_name)
                continue
            execution_order.append(provider_name)
            queries = step.get("queries") or [provider_name]
            max_results = step.get("max_results") or step.get("budget", 50)
            if remaining_budget is not None:
                max_results = min(max_results, remaining_budget)

            # Roda o provider (sync ou async, detectado por inspeção)
            try:
                candidates = self._invoke_provider(provider, queries, lead_context)
            except Exception:
                # Provider falhou — pula mas não derruba o batch
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
            if remaining_budget is not None:
                remaining_budget -= budget_used[provider_name]

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

    def _invoke_provider(
        self,
        provider: DiscoveryProvider,
        queries: List[str],
        lead_context: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Roda o provider em todas as queries, detectando sync/async.

        Suporta ambas as convenções sem exigir que o executor seja async.
        Para testabilidade, providers em tests podem ser sync.
        """
        import asyncio
        import inspect
        import threading

        all_results: List[Dict[str, Any]] = []
        for q in queries:
            res = provider.run(q, lead_context=lead_context)
            if inspect.isawaitable(res):
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    try:
                        res = asyncio.run(res)
                    except RuntimeError:
                        if inspect.iscoroutine(res):
                            res.close()
                        continue
                else:
                    # `execute()` sync dentro de ASGI: execute o awaitable
                    # numa thread isolada em vez de retornar dados vazios.
                    result_box: List[Any] = []
                    error_box: List[BaseException] = []

                    def _run() -> None:
                        try:
                            result_box.append(asyncio.run(res))
                        except BaseException as exc:  # noqa: BLE001
                            error_box.append(exc)

                    worker = threading.Thread(target=_run, daemon=True)
                    worker.start()
                    worker.join()
                    if error_box:
                        continue
                    res = result_box[0] if result_box else []
            all_results.extend(res or [])
        return all_results

    async def execute_async(
        self, plan: Dict[str, Any], lead_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Versão async do execute — para uso em pipeline real (não testes).

        Em ambiente async, sempre prefira este método ao execute().
        """
        import asyncio
        import inspect

        results_by_provider: Dict[str, List[Dict]] = {}
        execution_order: List[str] = []
        skipped: List[str] = []
        budget_used: Dict[str, int] = {}
        total_budget = plan.get("max_results") or plan.get("target_candidates")
        remaining_budget = int(total_budget) if total_budget is not None else None

        for step in plan.get("providers", []):
            provider_name = step.get("type")
            if remaining_budget is not None and remaining_budget <= 0:
                skipped.append(provider_name)
                continue
            provider = self.registry.get(provider_name)
            if provider is None:
                skipped.append(provider_name)
                continue
            execution_order.append(provider_name)
            queries = step.get("queries") or [provider_name]
            max_results = step.get("max_results") or step.get("budget", 50)
            if remaining_budget is not None:
                max_results = min(max_results, remaining_budget)

            all_results: List[Dict[str, Any]] = []
            for q in queries:
                try:
                    res = provider.run(q, lead_context=lead_context)
                    if inspect.isawaitable(res):
                        res = await res
                    all_results.extend(res or [])
                except Exception:
                    continue

            # Dedup intra-provider
            seen_keys = set()
            deduped = []
            for c in all_results:
                key = self._identity_key(c)
                if key and key in seen_keys:
                    continue
                seen_keys.add(key)
                deduped.append(c)
            results_by_provider[provider_name] = deduped[:max_results]
            budget_used[provider_name] = len(results_by_provider[provider_name])
            if remaining_budget is not None:
                remaining_budget -= budget_used[provider_name]

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
