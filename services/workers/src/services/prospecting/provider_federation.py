"""Contrato federado único para discovery/enrichment externo.

Novas fontes entram por capability e são planejadas pelo mesmo mecanismo de
custo/qualidade. O executor preserva `failed`, `empty`, `disabled` e quota como
estados diferentes; uma falha nunca é convertida silenciosamente em lista vazia.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Protocol, Sequence, runtime_checkable

from services.prospecting.provider_planner import ProviderPlanner, ProviderPolicy, ProviderQuality


@runtime_checkable
class FederatedProvider(Protocol):
    name: str
    capability: str
    policy: ProviderPolicy

    async def collect(self, request: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]: ...


@dataclass(frozen=True)
class FederationAttempt:
    provider: str
    status: str
    result_count: int = 0
    cost: float = 0.0
    error: str | None = None


class FederatedProviderRegistry:
    """Executa uma waterfall planejada sem acoplar provider à regra comercial."""

    def __init__(self, *, planner: ProviderPlanner | None = None) -> None:
        self._planner = planner or ProviderPlanner()
        self._providers: dict[tuple[str, str], FederatedProvider] = {}

    def register(self, provider: FederatedProvider) -> None:
        if not isinstance(provider, FederatedProvider):
            raise TypeError("provider não implementa o contrato federado")
        if provider.policy.provider != provider.name or provider.policy.capability != provider.capability:
            raise ValueError("policy deve identificar o mesmo provider/capability")
        self._providers[(provider.capability, provider.name)] = provider

    def capabilities(self) -> tuple[str, ...]:
        return tuple(sorted({capability for capability, _ in self._providers}))

    def providers_for(self, capability: str) -> tuple[str, ...]:
        return tuple(sorted(name for cap, name in self._providers if cap == capability))

    async def collect(
        self,
        capability: str,
        request: Mapping[str, Any],
        *,
        qualities: Sequence[ProviderQuality] = (),
        max_cost: float | None = None,
        max_providers: int | None = None,
        stop_when: Callable[[list[dict[str, Any]]], bool] | None = None,
    ) -> dict[str, Any]:
        policies = [provider.policy for (cap, _), provider in self._providers.items() if cap == capability]
        plan = self._planner.plan(policies, capability=capability, qualities=qualities, max_cost=max_cost)
        if max_providers is not None:
            plan = plan[:max(0, max_providers)]
        if not plan:
            return {"status": "disabled", "items": [], "attempts": [], "cost_spent": 0.0, "plan": []}

        items: list[dict[str, Any]] = []
        attempts: list[FederationAttempt] = []
        spent = 0.0
        for planned in plan:
            provider = self._providers[(capability, planned.provider)]
            if max_cost is not None and spent + planned.expected_cost > max_cost:
                attempts.append(FederationAttempt(planned.provider, "budget_exceeded"))
                continue
            try:
                raw = await provider.collect(request)
            except Exception as exc:  # provider boundary: status remains explicit
                attempts.append(FederationAttempt(planned.provider, getattr(exc, "status", "failed"), error=str(exc)[:500]))
                continue
            spent += planned.expected_cost
            if raw is None:
                attempts.append(FederationAttempt(planned.provider, "failed", cost=planned.expected_cost, error="provider_returned_none"))
                continue
            normalized = [dict(item) for item in raw if isinstance(item, Mapping)]
            if not normalized:
                attempts.append(FederationAttempt(planned.provider, "empty", cost=planned.expected_cost))
                continue
            items = self._merge(items, normalized, planned.provider)
            attempts.append(FederationAttempt(planned.provider, "success", len(normalized), planned.expected_cost))
            if stop_when and stop_when(items):
                break

        statuses = {attempt.status for attempt in attempts}
        status = "success" if items else "failed" if "failed" in statuses else "empty" if "empty" in statuses else "disabled"
        return {
            "status": status,
            "items": items,
            "attempts": [attempt.__dict__ for attempt in attempts],
            "cost_spent": round(spent, 6),
            "plan": [{"provider": item.provider, "score": item.score, "expected_cost": item.expected_cost, "reason": item.reason} for item in plan],
        }

    @staticmethod
    def _merge(existing: list[dict[str, Any]], incoming: list[dict[str, Any]], provider: str) -> list[dict[str, Any]]:
        result = list(existing)
        seen = {
            str(item.get("canonical_id") or item.get("id") or item.get("url") or item.get("email") or "")
            for item in result
        }
        for item in incoming:
            candidate = dict(item)
            candidate.setdefault("source", provider)
            key = str(candidate.get("canonical_id") or candidate.get("id") or candidate.get("url") or candidate.get("email") or "")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            result.append(candidate)
        return result
