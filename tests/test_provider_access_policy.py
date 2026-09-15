"""Política de acesso a providers: free-first/free-only por padrão, pago opt-in.

Convenção do repo: testes async rodam via `asyncio.run` dentro de teste
síncrono (sem plugin externo). Seams sob teste: `ProviderAccessPolicy`
(construtor + `allows`) e `FederatedProviderRegistry.collect`.
"""
from __future__ import annotations

import asyncio
import math

import pytest

from services.prospecting.provider_access_policy import ProviderAccessPolicy
from services.prospecting.provider_federation import FederatedProviderRegistry
from services.prospecting.provider_planner import ProviderPolicy


class _Provider:
    def __init__(
        self,
        name: str,
        cost: float,
        items: list[dict] | None = None,
        quota: int | None = None,
        exc: Exception | None = None,
        capability: str = "company_discovery",
    ):
        self.name = name
        self.capability = capability
        self.policy = ProviderPolicy(
            provider=name,
            capability=capability,
            cost_per_request=cost,
            quota_remaining=quota,
        )
        self.items = items if items is not None else [{"id": name}]
        self.exc = exc
        self.calls = 0

    async def collect(self, request):
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return self.items


def _statuses(result) -> list[tuple[str, str]]:
    return [(a["provider"], a["status"]) for a in result["attempts"]]


# --- construção da política ---


def test_free_only_rejects_nonzero_budget():
    with pytest.raises(ValueError):
        ProviderAccessPolicy(paid_providers_enabled=False, max_cost=1)


def test_policy_rejects_negative_budget():
    with pytest.raises(ValueError):
        ProviderAccessPolicy(paid_providers_enabled=True, max_cost=-0.01)


def test_policy_rejects_non_finite_budget():
    with pytest.raises(ValueError):
        ProviderAccessPolicy(paid_providers_enabled=True, max_cost=math.inf)
    with pytest.raises(ValueError):
        ProviderAccessPolicy(paid_providers_enabled=True, max_cost=math.nan)


def test_policy_rejects_non_finite_provider_cost():
    with pytest.raises(ValueError):
        ProviderPolicy(provider="x", capability="cap", cost_per_request=math.nan)
    with pytest.raises(ValueError):
        ProviderPolicy(provider="x", capability="cap", cost_per_request=math.inf)


def test_default_policy_is_free_only_with_zero_budget():
    policy = ProviderAccessPolicy()
    assert policy.paid_providers_enabled is False
    assert policy.max_cost == 0.0


# --- free-only / opt-in ---


def test_free_only_never_calls_paid_provider():
    async def scenario():
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
        return free, paid, result

    free, paid, result = asyncio.run(scenario())
    assert free.calls == 1
    assert paid.calls == 0
    assert result["cost_spent"] == 0
    assert ("premium", "paid_provider_disabled") in _statuses(result)


def test_free_provider_still_runs_under_free_only():
    async def scenario():
        registry = FederatedProviderRegistry()
        free = _Provider("public_web", 0)
        registry.register(free)
        return free, await registry.collect(
            "company_discovery", {}, access_policy=ProviderAccessPolicy()
        )

    free, result = asyncio.run(scenario())
    assert free.calls == 1
    assert result["status"] == "success"
    assert result["items"][0]["id"] == "public_web"


def test_paid_provider_needs_explicit_opt_in():
    async def scenario():
        registry = FederatedProviderRegistry()
        paid = _Provider("premium", 0.25)
        registry.register(paid)
        blocked = await registry.collect(
            "company_discovery", {}, access_policy=ProviderAccessPolicy()
        )
        allowed = await registry.collect(
            "company_discovery",
            {},
            access_policy=ProviderAccessPolicy(paid_providers_enabled=True, max_cost=0.25),
        )
        return paid, blocked, allowed

    paid, blocked, allowed = asyncio.run(scenario())
    assert paid.calls == 1
    assert ("premium", "paid_provider_disabled") in _statuses(blocked)
    assert allowed["status"] == "success"
    assert allowed["cost_spent"] == pytest.approx(0.25)


def test_individual_budget_caps_single_paid_provider():
    async def scenario():
        registry = FederatedProviderRegistry()
        expensive = _Provider("expensive", 0.80)
        registry.register(expensive)
        return expensive, await registry.collect(
            "company_discovery",
            {},
            access_policy=ProviderAccessPolicy(paid_providers_enabled=True, max_cost=0.50),
        )

    expensive, result = asyncio.run(scenario())
    assert expensive.calls == 0
    assert ("expensive", "budget_exceeded") in _statuses(result)
    assert result["cost_spent"] == 0


def test_paid_provider_requires_explicit_budget_and_respects_total_budget():
    async def scenario():
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
        return first, second, result

    first, second, result = asyncio.run(scenario())
    assert first.calls + second.calls == 1
    assert result["cost_spent"] == pytest.approx(0.4)
    assert any(status == "budget_exceeded" for _, status in _statuses(result))


def test_mixed_free_and_paid_with_opt_in_runs_free_first():
    async def scenario():
        registry = FederatedProviderRegistry()
        paid = _Provider("paid_z", 0.20)
        free = _Provider("free_a", 0)
        registry.register(paid)
        registry.register(free)
        return free, paid, await registry.collect(
            "company_discovery",
            {},
            access_policy=ProviderAccessPolicy(paid_providers_enabled=True, max_cost=1.0),
        )

    free, paid, result = asyncio.run(scenario())
    assert free.calls == 1
    assert paid.calls == 1
    assert result["status"] == "success"
    assert result["cost_spent"] == pytest.approx(0.20)
    executed = [p for p, s in _statuses(result) if s == "success"]
    assert executed[0] == "free_a"


# --- quota / legado ---


def test_exhausted_quota_is_explicit_and_provider_is_not_called():
    async def scenario():
        registry = FederatedProviderRegistry()
        provider = _Provider("free_tier", 0, quota=0)
        registry.register(provider)

        result = await registry.collect(
            "company_discovery",
            {},
            access_policy=ProviderAccessPolicy(),
        )
        return provider, result

    provider, result = asyncio.run(scenario())
    assert provider.calls == 0
    assert result["status"] == "disabled"
    assert _statuses(result) == [("free_tier", "quota_exhausted")]


def test_legacy_call_without_access_policy_preserves_previous_behavior():
    async def scenario():
        registry = FederatedProviderRegistry()
        paid = _Provider("legacy_paid", 0.10)
        registry.register(paid)
        return paid, await registry.collect("company_discovery", {})

    paid, result = asyncio.run(scenario())
    assert paid.calls == 1
    assert result["status"] == "success"
    assert result["cost_spent"] == pytest.approx(0.1)


# --- falha / vazio / None ---


def test_failing_provider_does_not_hide_failure_and_waterfall_continues():
    async def scenario():
        registry = FederatedProviderRegistry()
        broken = _Provider("broken", 0, exc=RuntimeError("offline"))
        backup = _Provider("backup", 0)
        registry.register(broken)
        registry.register(backup)
        return broken, backup, await registry.collect(
            "company_discovery", {}, access_policy=ProviderAccessPolicy()
        )

    broken, backup, result = asyncio.run(scenario())
    assert broken.calls == 1
    assert backup.calls == 1
    assert result["status"] == "success"
    assert ("broken", "failed") in _statuses(result)
    assert ("backup", "success") in _statuses(result)


def test_empty_result_is_not_a_failure():
    async def scenario():
        registry = FederatedProviderRegistry()
        provider = _Provider("sparse", 0, items=[])
        registry.register(provider)
        return provider, await registry.collect(
            "company_discovery", {}, access_policy=ProviderAccessPolicy()
        )

    provider, result = asyncio.run(scenario())
    assert provider.calls == 1
    assert result["status"] == "empty"
    assert result["items"] == []
    assert _statuses(result) == [("sparse", "empty")]


def test_provider_returning_none_is_a_failure_not_empty():
    async def scenario():
        registry = FederatedProviderRegistry()
        provider = _Provider("none_provider", 0, items=[])
        provider.items = None  # type: ignore[assignment]
        registry.register(provider)
        return provider, await registry.collect(
            "company_discovery", {}, access_policy=ProviderAccessPolicy()
        )

    provider, result = asyncio.run(scenario())
    assert provider.calls == 1
    assert result["status"] == "failed"
    assert result["items"] == []
    assert _statuses(result) == [("none_provider", "failed")]


def test_exception_status_can_never_claim_success_or_empty():
    class _WeirdError(Exception):
        def __init__(self):
            super().__init__("boom")
            self.status = "success"  # noqa: SLF001 — simula provider mentiroso

    async def scenario():
        registry = FederatedProviderRegistry()
        provider = _Provider("weird", 0, exc=_WeirdError())
        registry.register(provider)
        return await registry.collect(
            "company_discovery", {}, access_policy=ProviderAccessPolicy()
        )

    result = asyncio.run(scenario())
    assert result["status"] == "failed"
    assert _statuses(result) == [("weird", "failed")]
    assert result["items"] == []


def test_informative_exception_status_is_preserved():
    exc = RuntimeError("throttled")
    exc.status = "rate_limited"  # type: ignore[attr-defined]

    async def scenario():
        registry = FederatedProviderRegistry()
        provider = _Provider("throttled", 0, exc=exc)
        registry.register(provider)
        return await registry.collect(
            "company_discovery", {}, access_policy=ProviderAccessPolicy()
        )

    result = asyncio.run(scenario())
    assert _statuses(result) == [("throttled", "rate_limited")]
    assert result["status"] == "failed"


# --- stop / limites / ordenação ---


def test_stop_when_halts_waterfall_and_marks_remainder_skipped():
    async def scenario():
        registry = FederatedProviderRegistry()
        first = _Provider("a_first", 0)
        second = _Provider("b_second", 0)
        third = _Provider("c_third", 0)
        registry.register(first)
        registry.register(second)
        registry.register(third)
        result = await registry.collect(
            "company_discovery",
            {},
            access_policy=ProviderAccessPolicy(),
            stop_when=lambda items: len(items) >= 1,
        )
        return first, second, third, result

    first, second, third, result = asyncio.run(scenario())
    assert first.calls == 1
    assert second.calls == 0
    assert third.calls == 0
    assert result["status"] == "success"
    assert ("b_second", "skipped") in _statuses(result)
    assert ("c_third", "skipped") in _statuses(result)


def test_max_providers_truncates_waterfall():
    async def scenario():
        registry = FederatedProviderRegistry()
        providers = [_Provider(f"p{i}", 0) for i in range(3)]
        for provider in providers:
            registry.register(provider)
        result = await registry.collect(
            "company_discovery",
            {},
            access_policy=ProviderAccessPolicy(),
            max_providers=2,
        )
        return providers, result

    providers, result = asyncio.run(scenario())
    assert [p.calls for p in providers].count(1) == 2
    assert len([a for a in result["attempts"] if a["status"] == "success"]) == 2


def test_max_providers_zero_runs_nothing():
    async def scenario():
        registry = FederatedProviderRegistry()
        provider = _Provider("solo", 0)
        registry.register(provider)
        return provider, await registry.collect(
            "company_discovery",
            {},
            access_policy=ProviderAccessPolicy(),
            max_providers=0,
        )

    provider, result = asyncio.run(scenario())
    assert provider.calls == 0
    assert result["status"] == "disabled"
    assert result["items"] == []


def test_ordering_is_deterministic_across_runs():
    def run_once():
        async def scenario():
            registry = FederatedProviderRegistry()
            registry.register(_Provider("zeta", 0.10))
            registry.register(_Provider("alpha", 0.10))
            registry.register(_Provider("free_b", 0))
            registry.register(_Provider("free_a", 0))
            return await registry.collect(
                "company_discovery",
                {},
                access_policy=ProviderAccessPolicy(
                    paid_providers_enabled=True, max_cost=1.0
                ),
            )

        return asyncio.run(scenario())

    first = [p["provider"] for p in run_once()["plan"]]
    second = [p["provider"] for p in run_once()["plan"]]
    assert first == second
    assert first[:2] == ["free_a", "free_b"]
    assert set(first[2:]) == {"alpha", "zeta"}


# --- bloqueios totais e status agregado ---


def test_all_providers_blocked_runs_nothing_and_reports_disabled():
    async def scenario():
        registry = FederatedProviderRegistry()
        paid = _Provider("paid_a", 0.30)
        no_quota = _Provider("free_b", 0, quota=0)
        registry.register(paid)
        registry.register(no_quota)
        return paid, no_quota, await registry.collect(
            "company_discovery", {}, access_policy=ProviderAccessPolicy()
        )

    paid, no_quota, result = asyncio.run(scenario())
    assert paid.calls == 0
    assert no_quota.calls == 0
    assert result["status"] == "disabled"
    assert result["items"] == []
    assert result["cost_spent"] == 0
    assert ("paid_a", "paid_provider_disabled") in _statuses(result)
    assert ("free_b", "quota_exhausted") in _statuses(result)


def test_empty_result_alongside_blocked_provider_is_not_pure_empty():
    """UNKNOWN != FALSE: `empty` exige todas as fontes consultadas sem achado."""
    async def scenario():
        registry = FederatedProviderRegistry()
        registry.register(_Provider("consulted_empty", 0, items=[]))
        registry.register(_Provider("not_consulted_paid", 0.25))
        return await registry.collect(
            "company_discovery", {}, access_policy=ProviderAccessPolicy()
        )

    result = asyncio.run(scenario())
    assert result["status"] == "disabled"
    assert result["items"] == []
    assert ("consulted_empty", "empty") in _statuses(result)
    assert ("not_consulted_paid", "paid_provider_disabled") in _statuses(result)


def test_quota_exhausted_alongside_empty_is_not_pure_empty():
    async def scenario():
        registry = FederatedProviderRegistry()
        registry.register(_Provider("no_quota", 0, quota=0))
        registry.register(_Provider("consulted_empty", 0, items=[]))
        return await registry.collect(
            "company_discovery", {}, access_policy=ProviderAccessPolicy()
        )

    result = asyncio.run(scenario())
    assert result["status"] == "disabled"
    assert ("no_quota", "quota_exhausted") in _statuses(result)
    assert ("consulted_empty", "empty") in _statuses(result)


def test_failure_alongside_empty_reports_failure():
    async def scenario():
        registry = FederatedProviderRegistry()
        registry.register(_Provider("broken", 0, exc=RuntimeError("offline")))
        registry.register(_Provider("sparse", 0, items=[]))
        return await registry.collect(
            "company_discovery", {}, access_policy=ProviderAccessPolicy()
        )

    result = asyncio.run(scenario())
    assert result["status"] == "failed"
    assert result["items"] == []


def test_budget_block_alongside_success_keeps_evidence_of_block():
    async def scenario():
        registry = FederatedProviderRegistry()
        registry.register(_Provider("cheap_hit", 0.10))
        registry.register(_Provider("pricey", 0.45))
        return await registry.collect(
            "company_discovery",
            {},
            access_policy=ProviderAccessPolicy(paid_providers_enabled=True, max_cost=0.50),
        )

    result = asyncio.run(scenario())
    assert result["status"] == "success"
    assert any(status == "budget_exceeded" for _, status in _statuses(result))
    assert result["cost_spent"] == pytest.approx(0.10)


def test_no_registered_providers_reports_disabled_without_attempts():
    async def scenario():
        return await FederatedProviderRegistry().collect(
            "company_discovery", {}, access_policy=ProviderAccessPolicy()
        )

    result = asyncio.run(scenario())
    assert result["status"] == "disabled"
    assert result["attempts"] == []
    assert result["items"] == []
