"""Política de execução de providers externos.

A política é deliberadamente independente de provider concreto. Ela decide se
uma chamada é elegível antes de qualquer I/O e mantém providers pagos opt-in.
O custo é uma estimativa de planejamento na mesma unidade usada pela
telemetria do caller — não é uma fatura auditável (`expected != billed`).
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from services.prospecting.provider_planner import ProviderPolicy


@dataclass(frozen=True)
class ProviderAccessPolicy:
    """Limites de uma execução federada.

    `paid_providers_enabled=False` é o default seguro para novos fluxos. O
    registry federado só aplica esta regra quando a política é fornecida, para
    preservar consumidores legados durante a migração gradual.

    `max_cost` tem semântica dupla e intencional: é o teto por chamada (um
    provider com `cost_per_request` maior é inelegível) e o teto cumulativo
    da waterfall (a soma dos custos esperados das chamadas executadas não
    ultrapassa o teto). O valor mais restritivo entre a política e o
    `max_cost` legado do `collect` sempre vence.
    """

    paid_providers_enabled: bool = False
    max_cost: float = 0.0

    def __post_init__(self) -> None:
        if not isfinite(self.max_cost) or self.max_cost < 0:
            raise ValueError("max_cost deve ser um valor finito não negativo")
        if not self.paid_providers_enabled and self.max_cost != 0:
            raise ValueError("max_cost deve ser zero quando providers pagos estão desativados")

    def allows(self, provider: ProviderPolicy) -> tuple[bool, str]:
        if not provider.enabled:
            return False, "provider_disabled"
        if provider.quota_remaining is not None and provider.quota_remaining <= 0:
            return False, "quota_exhausted"
        if provider.cost_per_request <= 0:
            return True, "free"
        if not self.paid_providers_enabled:
            return False, "paid_provider_disabled"
        if provider.cost_per_request > self.max_cost:
            return False, "budget_exceeded"
        return True, "allowed"
