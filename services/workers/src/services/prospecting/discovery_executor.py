"""Discovery Executor (Fase D — consolidação §Fase D).

Contract de provider + registry + executor. O pipeline_worker não chama
mais providers diretamente — passa o `discovery_plan` (saída do
DiscoveryPlanner) para o executor, que sabe qual provider rodar,
em que ordem, com qual budget e dedup.

Critério da Fase D: "Alterar OfferProfile.discovery muda a estratégia de
descoberta sem editar pipeline_worker" — providers plugados via
registry; adicionar novo provider = criar adapter + registrar.
"""
import time
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from services.company_identity_service import CompanyIdentityResolver


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
        self.identity_resolver = CompanyIdentityResolver()

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

            candidates = [
                {
                    **candidate,
                    "provider": candidate.get("provider") or provider_name,
                    "provider_query": candidate.get("provider_query") or queries[0],
                }
                for candidate in candidates
            ]

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
        provider_status: Dict[str, str] = {}
        provider_errors: Dict[str, str] = {}
        provider_metrics: Dict[str, Dict[str, Any]] = {}
        total_budget = plan.get("max_results") or plan.get("target_candidates")
        remaining_budget = int(total_budget) if total_budget is not None else None

        for step in plan.get("providers", []):
            provider_name = step.get("type")
            if remaining_budget is not None and remaining_budget <= 0:
                skipped.append(provider_name)
                provider_status[provider_name] = "skipped"
                provider_metrics[provider_name] = self._provider_metric("skipped", 0, 0, None, False)
                continue
            provider = self.registry.get(provider_name)
            if provider is None:
                skipped.append(provider_name)
                provider_status[provider_name] = "skipped"
                provider_metrics[provider_name] = self._provider_metric("skipped", 0, 0, None, False)
                continue
            execution_order.append(provider_name)
            queries = step.get("queries") or [provider_name]
            max_results = step.get("max_results") or step.get("budget", 50)
            if remaining_budget is not None:
                max_results = min(max_results, remaining_budget)

            all_results: List[Dict[str, Any]] = []
            started = time.perf_counter()
            first_error: Optional[Exception] = None
            for q in queries:
                try:
                    res = provider.run(q, lead_context=lead_context)
                    if inspect.isawaitable(res):
                        res = await res
                    all_results.extend(
                        {
                            **candidate,
                            "provider": candidate.get("provider") or provider_name,
                            "provider_query": candidate.get("provider_query") or q,
                        }
                        for candidate in (res or [])
                    )
                except Exception as exc:  # noqa: BLE001 — contrato registra a falha
                    first_error = first_error or exc
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
            if first_error is not None:
                provider_status[provider_name] = "failed"
                provider_errors[provider_name] = f"{type(first_error).__name__}: {first_error}"
                metric_status = "failed"
            else:
                provider_status[provider_name] = "success" if deduped else "empty"
                metric_status = provider_status[provider_name]
            provider_metrics[provider_name] = self._provider_metric(
                metric_status, len(results_by_provider[provider_name]), started,
                type(first_error).__name__ if first_error else None,
                self._is_retryable(first_error) if first_error else False,
            )

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
            "provider_status": provider_status,
            "provider_errors": provider_errors,
            "provider_metrics": provider_metrics,
        }

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Classifica falhas transitórias sem esconder erros do provider."""
        message = str(exc).lower()
        return any(token in message for token in (
            "429", "408", "500", "502", "503", "504", "timeout",
            "timed out", "temporar", "indisponível",
        ))

    @staticmethod
    def _provider_metric(
        status: str,
        result_count: int,
        started: float,
        error_code: Optional[str],
        retryable: bool,
    ) -> Dict[str, Any]:
        """Retorna a forma comum de telemetria por provider."""
        elapsed = int(max(0, (time.perf_counter() - started) * 1000)) if started else 0
        return {
            "status": status,
            "result_count": result_count,
            "duration_ms": elapsed,
            "budget_used": result_count,
            "error_code": error_code,
            "retryable": retryable,
        }

    def _identity_key(self, candidate: Dict[str, Any]) -> Optional[str]:
        """Chave de identidade para dedup (primeira chave disponível)."""
        for k in self.dedup_keys:
            if k in candidate and candidate[k]:
                return f"{k}:{candidate[k]}"
        return None

    def _dedup(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Dedup por identidade confirmada e preserva provenance de fontes."""
        seen: set = set()
        out: List[Dict[str, Any]] = []
        for c in candidates:
            key = self._identity_key(c)
            match = None
            match_result = None
            for existing in out:
                identity = self.identity_resolver.resolve(existing, [c])
                if identity.status == "confirmed":
                    match = existing
                    match_result = identity
                    break
            if match is not None:
                self._merge_identity(match, c, match_result)
                continue
            if key and key in seen:
                previous = next((item for item in out if self._identity_key(item) == key), None)
                if previous is None or not self._conflicting_strong_identity(previous, c):
                    continue
            if key:
                seen.add(key)
            c.setdefault("identity_resolution", {
                "status": "new",
                "matched_by": None,
                "confidence": 0.0,
                "auto_merge": False,
            })
            c.setdefault("provenance", self._candidate_provenance(c))
            out.append(c)
        return out

    @staticmethod
    def _conflicting_strong_identity(
        left: Dict[str, Any],
        right: Dict[str, Any],
    ) -> bool:
        """Evita que o fallback por nome esconda chaves fortes diferentes."""
        strong_values = []
        for keys in (("cnpj",), ("normalized_domain",), ("place_id", "place_id_candidate")):
            left_value = next((left.get(key) for key in keys if left.get(key)), None)
            right_value = next((right.get(key) for key in keys if right.get(key)), None)
            if left_value:
                strong_values.append(("left", str(left_value).strip()))
            if right_value:
                strong_values.append(("right", str(right_value).strip()))
        return bool(
            strong_values
            and any(
                left_value != right_value
                for index, (side, left_value) in enumerate(strong_values)
                for other_side, right_value in strong_values[index + 1:]
                if side != other_side
            )
        )

    def _merge_identity(
        self,
        target: Dict[str, Any],
        incoming: Dict[str, Any],
        match_result: Any,
    ) -> None:
        """Mescla dados não vazios e provenance de candidatos confirmados."""
        for key, value in incoming.items():
            if value and not target.get(key):
                target[key] = value
        target["identity_resolution"] = match_result.to_dict()
        target["provenance"] = self._merge_provenance(
            target.get("provenance") or self._candidate_provenance(target),
            self._candidate_provenance(incoming),
        )
        queries = list(dict.fromkeys([
            *(target.get("source_queries") or []),
            *(incoming.get("source_queries") or []),
            *([incoming["provider_query"]] if incoming.get("provider_query") else []),
        ]))
        if queries:
            target["source_queries"] = queries

    @staticmethod
    def _candidate_provenance(candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai provenance básica sem alterar o objeto original."""
        return {
            "providers": [candidate["provider"]] if candidate.get("provider") else [],
            "provider_queries": [candidate["provider_query"]] if candidate.get("provider_query") else [],
            "provider_candidate_ids": [
                str(candidate.get("provider_candidate_id") or candidate.get("id"))
            ] if candidate.get("provider_candidate_id") or candidate.get("id") else [],
        }

    @staticmethod
    def _merge_provenance(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
        """Une listas de provenance preservando a ordem de descoberta."""
        return {
            key: list(dict.fromkeys([*(left.get(key) or []), *(right.get(key) or [])]))
            for key in ("providers", "provider_queries", "provider_candidate_ids")
        }
