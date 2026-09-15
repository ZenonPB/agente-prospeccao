"""Contrato federado único para discovery/enrichment externo.

Novas fontes entram por capability e são planejadas pelo mesmo mecanismo de
custo/qualidade. O executor preserva estados de falha, vazio, bloqueio e quota;
uma falha nunca é convertida silenciosamente em lista vazia.

Status agregado (`UNKNOWN != FALSE`): `empty` significa que todas as fontes
consultadas responderam sem achados. Qualquer bloqueio (provider desativado,
quota, paid sem opt-in, orçamento) ou falha ao lado de um `empty` impede o
agregado de alegar `empty` — ausência de consulta não é ausência de dado.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol, Sequence, runtime_checkable

from services.prospecting.provider_access_policy import ProviderAccessPolicy
from services.prospecting.provider_planner import ProviderPlanner, ProviderPolicy, ProviderQuality

# Tentativas que significam "a fonte nem foi consultada".
_BLOCKED_STATUSES = frozenset({
    "provider_disabled",
    "quota_exhausted",
    "paid_provider_disabled",
    "budget_exceeded",
    "skipped",
})


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
        access_policy: ProviderAccessPolicy | None = None,
        max_providers: int | None = None,
        stop_when: Callable[[list[dict[str, Any]]], bool] | None = None,
    ) -> dict[str, Any]:
        """Executa providers elegíveis.

        `access_policy=None` preserva o contrato legado. Novos fluxos devem
        fornecer uma política explícita; seu default é free-only.

        `cost_spent` soma os custos *esperados* das chamadas iniciadas,
        incluindo tentativas que falharam (provisão conservadora: uma chamada
        paga tentada pode ter sido cobrada). É estimativa de planejamento,
        não valor faturado.
        """
        policies = [provider.policy for (cap, _), provider in self._providers.items() if cap == capability]
        blocked: list[FederationAttempt] = []
        if access_policy is not None:
            eligible: list[ProviderPolicy] = []
            for policy in policies:
                allowed, reason = access_policy.allows(policy)
                if allowed:
                    eligible.append(policy)
                else:
                    blocked.append(FederationAttempt(policy.provider, reason))
            policies = eligible
            effective_max_cost = access_policy.max_cost
            if max_cost is not None:
                effective_max_cost = min(effective_max_cost, max_cost)
        else:
            effective_max_cost = max_cost

        if effective_max_cost is not None:
            affordable: list[ProviderPolicy] = []
            for policy in policies:
                if policy.cost_per_request > effective_max_cost:
                    blocked.append(FederationAttempt(policy.provider, "budget_exceeded"))
                else:
                    affordable.append(policy)
            policies = affordable

        plan = self._planner.plan(
            policies,
            capability=capability,
            qualities=qualities,
            max_cost=effective_max_cost,
        )
        if max_providers is not None:
            plan = plan[:max(0, max_providers)]
        if not plan:
            return {
                "status": "disabled",
                "items": [],
                "attempts": [attempt.__dict__ for attempt in blocked],
                "cost_spent": 0.0,
                "plan": [],
            }

        items: list[dict[str, Any]] = []
        attempts: list[FederationAttempt] = list(blocked)
        spent = 0.0
        for index, planned in enumerate(plan):
            provider = self._providers[(capability, planned.provider)]
            if effective_max_cost is not None and spent + planned.expected_cost > effective_max_cost:
                attempts.append(FederationAttempt(planned.provider, "budget_exceeded"))
                continue
            spent += planned.expected_cost  # reserva conservadora antes do I/O
            try:
                raw = await provider.collect(request)
            except Exception as exc:  # provider boundary: status remains explicit
                attempts.append(FederationAttempt(
                    planned.provider, _exc_status(exc), error=str(exc)[:500],
                ))
                continue
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
                for skipped in plan[index + 1:]:
                    attempts.append(FederationAttempt(skipped.provider, "skipped"))
                break

        status = _aggregate_status(attempts, has_items=bool(items))
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


def _exc_status(exc: Exception) -> str:
    """Traduz a exceção do provider em status observável sem permitir mentira.

    Uma chamada que levantou exceção nunca produziu dado, então nunca pode ser
    registrada como `success` ou `empty`. Sinais informativos (ex. timeout,
    rate_limited, quota_exhausted) passam para observabilidade; qualquer outro
    valor vira `failed` (fail-closed).
    """
    status = getattr(exc, "status", "failed")
    if not isinstance(status, str) or not status.strip():
        return "failed"
    if status in ("success", "empty"):
        return "failed"
    return status


def _aggregate_status(attempts: Sequence[FederationAttempt], *, has_items: bool) -> str:
    """Agrega tentativas sem esconder bloqueio ou falha atrás de `empty`.

    `empty` exige que todas as fontes consultadas tenham respondido sem
    achados. Se alguma fonte falhou, não foi consultada ou retornou estado
    desconhecido, o agregado reflete isso em vez de alegar ausência de dado.
    """
    if has_items:
        return "success"
    statuses = {attempt.status for attempt in attempts}
    if not statuses:
        return "disabled"
    if statuses <= {"empty"}:
        return "empty"
    if statuses <= ({"empty"} | _BLOCKED_STATUSES):
        return "disabled"
    return "failed"
