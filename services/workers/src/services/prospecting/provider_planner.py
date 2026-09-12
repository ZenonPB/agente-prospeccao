"""Planejamento determinístico de providers por capability.

A ordem de execução é uma decisão de política, não de rede. O planner nunca
faz I/O: ele recebe metadados conhecidos (custo, cobertura, precisão, saúde e
quota) e devolve uma waterfall explicável. Métricas desconhecidas permanecem
explícitas e recebem priors conservadores em vez de virarem zero.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ProviderPolicy:
    provider: str
    capability: str
    cost_per_request: float = 0.0
    expected_coverage: float | None = None
    expected_precision: float | None = None
    rate_limit_per_minute: int | None = None
    quota_remaining: int | None = None
    enabled: bool = True
    priority: int = 100

    def __post_init__(self) -> None:
        if not self.provider.strip() or not self.capability.strip():
            raise ValueError("provider e capability são obrigatórios")
        if self.cost_per_request < 0:
            raise ValueError("cost_per_request não pode ser negativo")
        for name, value in (("expected_coverage", self.expected_coverage), ("expected_precision", self.expected_precision)):
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name} deve estar entre 0 e 1")
        if self.quota_remaining is not None and self.quota_remaining < 0:
            raise ValueError("quota_remaining não pode ser negativa")


@dataclass(frozen=True)
class ProviderQuality:
    provider: str
    capability: str
    sample_size: int = 0
    coverage: float | None = None
    precision: float | None = None
    commercial_yield: float | None = None

    def __post_init__(self) -> None:
        if self.sample_size < 0:
            raise ValueError("sample_size não pode ser negativo")
        for name, value in (("coverage", self.coverage), ("precision", self.precision), ("commercial_yield", self.commercial_yield)):
            if value is not None and not 0 <= value <= 1:
                raise ValueError(f"{name} deve estar entre 0 e 1")


@dataclass(frozen=True)
class PlannedProvider:
    provider: str
    capability: str
    score: float
    expected_cost: float
    reason: str


class ProviderPlanner:
    """Ordena providers pelo valor esperado, preservando free-first e limites."""

    DEFAULT_COVERAGE = 0.45
    DEFAULT_PRECISION = 0.65
    MIN_SAMPLE_FOR_LEARNED_QUALITY = 20

    def plan(
        self,
        policies: Iterable[ProviderPolicy],
        *,
        capability: str,
        qualities: Iterable[ProviderQuality] = (),
        max_cost: float | None = None,
        prefer_free: bool = True,
    ) -> list[PlannedProvider]:
        if max_cost is not None and max_cost < 0:
            raise ValueError("max_cost não pode ser negativo")

        quality_by_key = {(q.provider, q.capability): q for q in qualities}
        candidates: list[PlannedProvider] = []
        for policy in policies:
            if policy.capability != capability or not policy.enabled:
                continue
            if policy.quota_remaining is not None and policy.quota_remaining <= 0:
                continue
            if max_cost is not None and policy.cost_per_request > max_cost:
                continue

            quality = quality_by_key.get((policy.provider, policy.capability))
            learned = quality if quality and quality.sample_size >= self.MIN_SAMPLE_FOR_LEARNED_QUALITY else None
            coverage = (
                learned.coverage if learned and learned.coverage is not None
                else policy.expected_coverage if policy.expected_coverage is not None
                else self.DEFAULT_COVERAGE
            )
            precision = (
                learned.precision if learned and learned.precision is not None
                else policy.expected_precision if policy.expected_precision is not None
                else self.DEFAULT_PRECISION
            )
            commercial = learned.commercial_yield if learned and learned.commercial_yield is not None else 0.5
            value = (0.40 * coverage) + (0.45 * precision) + (0.15 * commercial)
            # custo é penalidade suave; providers gratuitos não recebem bônus
            # artificial infinito e continuam comparáveis por qualidade.
            cost_penalty = 1.0 + max(0.0, policy.cost_per_request)
            score = value / cost_penalty
            reason = (
                f"cobertura {coverage:.0%}, precisão {precision:.0%}, "
                f"custo {policy.cost_per_request:.4f}"
            )
            candidates.append(PlannedProvider(
                provider=policy.provider,
                capability=policy.capability,
                score=round(score, 6),
                expected_cost=policy.cost_per_request,
                reason=reason,
            ))

        if prefer_free:
            candidates.sort(key=lambda item: (item.expected_cost > 0, -item.score, item.expected_cost, item.provider))
        else:
            candidates.sort(key=lambda item: (-item.score, item.expected_cost, item.provider))
        return candidates

    @staticmethod
    def waterfall(plan: Iterable[PlannedProvider], *, max_providers: int | None = None) -> tuple[str, ...]:
        providers = [item.provider for item in plan]
        if max_providers is not None:
            if max_providers < 1:
                return ()
            providers = providers[:max_providers]
        return tuple(providers)
