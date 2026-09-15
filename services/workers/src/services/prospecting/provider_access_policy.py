"""Política de execução de providers externos.

A política é deliberadamente independente de provider concreto. Ela decide se
uma chamada é elegível antes de qualquer I/O e mantém providers pagos opt-in.
O custo é expresso na mesma unidade monetária usada pela telemetria do caller.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from services.prospecting.provider_planner import ProviderPolicy


class ProviderBilling(str, Enum):
    FREE = "free"
    FREE_TIER = "free_tier"
    PAID = "paid"


@dataclass(frozen=True)
class ProviderAccessPolicy:
    """Limites de uma execução federada.

    `paid_providers_enabled=False` é o default seguro para novos fluxos. O
    registry federado só aplica esta regra quando a política é fornecida, para
    preservar consumidores legados durante a migração gradual.
    """

    paid_providers_enabled: bool = False
    max_cost: float = 0.0

    def __post_init__(self) -> None:
        if self.max_cost < 0:
            raise ValueError("max_cost não pode ser negativo")
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
