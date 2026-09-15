from __future__ import annotations

import pytest

from services.prospecting.provider_access_policy import ProviderAccessPolicy
from services.prospecting.provider_federation import FederatedProviderRegistry
from services.prospecting.provider_planner import ProviderPolicy


class _Provider:
    def __init__(self, name: str, cost: float, items: list[dict] | None = None, quota: int | None = None):
        self.name = name
        self.capability = "company_discovery"
        self.policy = ProviderPolicy(
            provider=name,
            capability=self.capability,
            cost_per_request=cost,
            quota_remaining=quota,
        )
        self.items = items if items is not None else [{"id": name}]
        self.calls = 0

    async def collect(self, request):
        self.calls += 1
        return self.items


def test_free_only_rejects_nonzero_budget():
    with pytest.raises(ValueError):
        ProviderAccessPolicy(paid_providers_enabled=False, max_cost=1)


@pytest.mark.asyncio
async def test_free_only_never_calls_paid_provider():
    registry = FederatedProviderRegistry()
    free = _Provider("public_web", 0)
    paid = _Provider("premium", 0.25)
    registry.register(free)
    registry.register(paid)

    result = await registry.collect(
        "company_discovery",
        {},
        access_policy=ProviderAccessPolicy(),
    )

    assert free.calls == 1
    assert paid.calls == 0
    assert result["cost_spent"] == 0
    assert any(a["provider"] == "premium" and a["status"] == "paid_provider_disabled" for a in result["attempts"])


@pytest.mark.asyncio
async def test_paid_provider_requires_explicit_budget_and_respects_total_budget():
    registry = FederatedProviderRegistry()
    first = _Provider("paid_a", 0.40, items=[])
    second = _Provider("paid_b", 0.40)
    registry.register(first)
    registry.register(second)

    result = await registry.collect(
        "company_discovery",
        {},
        access_policy=ProviderAccessPolicy(paid_providers_enabled=True, max_cost=0.50),
    )

    assert first.calls + second.calls == 1
    assert result["cost_spent"] == 0.4
    assert any(a["status"] == "budget_exceeded" for a in result["attempts"])


@pytest.mark.asyncio
async def test_exhausted_quota_is_explicit_and_provider_is_not_called():
    registry = FederatedProviderRegistry()
    provider = _Provider("free_tier", 0, quota=0)
    registry.register(provider)

    result = await registry.collect(
        "company_discovery",
        {},
        access_policy=ProviderAccessPolicy(),
    )

    assert provider.calls == 0
    assert result["status"] == "disabled"
    assert result["attempts"][0]["status"] == "quota_exhausted"


@pytest.mark.asyncio
async def test_legacy_call_without_access_policy_preserves_previous_behavior():
    registry = FederatedProviderRegistry()
    paid = _Provider("legacy_paid", 0.10)
    registry.register(paid)

    result = await registry.collect("company_discovery", {})

    assert paid.calls == 1
    assert result["status"] == "success"
    assert result["cost_spent"] == 0.1
