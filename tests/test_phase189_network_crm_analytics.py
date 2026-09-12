import asyncio
import os
import sys

import httpx

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKERS = os.path.join(ROOT, "services", "workers", "src")
API = os.path.join(ROOT, "services", "api")
for path in (WORKERS, API):
    if path not in sys.path:
        sys.path.insert(0, path)

from services.crm_adapters import (  # noqa: E402
    CRMEntitySnapshot,
    HubSpotCRMAdapter,
    PipedriveCRMAdapter,
    SalesforceCRMAdapter,
    build_crm_adapter,
)
from services.prospecting.provider_federation import FederatedProviderRegistry  # noqa: E402
from services.prospecting.provider_planner import (  # noqa: E402
    ProviderPlanner,
    ProviderPolicy,
    ProviderQuality,
)
from src.services.commercial_intelligence_service import _outcome_bucket, _signals  # noqa: E402


def test_provider_planner_is_free_first_and_quality_aware():
    planner = ProviderPlanner()
    policies = [
        ProviderPolicy("free-site", "people", 0, expected_coverage=0.25, expected_precision=0.7),
        ProviderPolicy("paid-a", "people", 0.2, expected_coverage=0.8, expected_precision=0.85),
        ProviderPolicy("paid-b", "people", 0.1, expected_coverage=0.6, expected_precision=0.8),
    ]
    qualities = [ProviderQuality("paid-b", "people", sample_size=40, coverage=0.9, precision=0.95, commercial_yield=0.8)]
    plan = planner.plan(policies, capability="people", qualities=qualities)
    assert plan[0].provider == "free-site"
    assert plan[1].provider == "paid-b"
    assert plan[2].provider == "paid-a"
    assert "cobertura" in plan[1].reason


def test_provider_planner_blocks_disabled_quota_and_budget():
    planner = ProviderPlanner()
    policies = [
        ProviderPolicy("disabled", "jobs", enabled=False),
        ProviderPolicy("no-quota", "jobs", quota_remaining=0),
        ProviderPolicy("too-expensive", "jobs", cost_per_request=2),
        ProviderPolicy("allowed", "jobs", cost_per_request=0.1),
    ]
    plan = planner.plan(policies, capability="jobs", max_cost=0.5)
    assert [item.provider for item in plan] == ["allowed"]


class _Provider:
    def __init__(self, name, capability, policy, result=None, exc=None):
        self.name = name
        self.capability = capability
        self.policy = policy
        self._result = result
        self._exc = exc

    async def collect(self, request):
        if self._exc:
            raise self._exc
        return self._result


def test_federation_fails_over_without_hiding_failure():
    async def scenario():
        registry = FederatedProviderRegistry()
        registry.register(_Provider("first", "events", ProviderPolicy("first", "events", 0), exc=RuntimeError("offline")))
        registry.register(_Provider("second", "events", ProviderPolicy("second", "events", 0.1), result=[{"id": "evt-1", "name": "Evento"}]))
        result = await registry.collect("events", {"city": "Araraquara"})
        assert result["status"] == "success"
        assert result["items"][0]["source"] == "second"
        assert [item["status"] for item in result["attempts"]] == ["failed", "success"]
    asyncio.run(scenario())


def test_hubspot_adapter_maps_create_without_leaking_token():
    requests = []

    async def handler(request: httpx.Request):
        requests.append(request)
        return httpx.Response(201, json={"id": "123", "updatedAt": "2026-09-12T10:00:00Z"})

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = HubSpotCRMAdapter("super-secret", client=client)
            result = await adapter.upsert(
                CRMEntitySnapshot("company", "local-1", "org-1", fields={"name": "Empresa"}),
                idempotency_key="sync-1",
            )
            assert result.status == "success"
            assert result.remote_entity_id == "123"
            assert requests[0].headers["Authorization"] == "Bearer super-secret"
            assert "super-secret" not in str(result)
    asyncio.run(scenario())


def test_pipedrive_adapter_rejects_http_base_url():
    try:
        PipedriveCRMAdapter("token-123", base_url="http://example.com")
    except ValueError as exc:
        assert "HTTPS" in str(exc)
    else:
        raise AssertionError("HTTP deveria ser rejeitado")


def test_salesforce_requires_instance_url():
    try:
        build_crm_adapter("salesforce", "token-123")
    except ValueError as exc:
        assert "URL HTTPS" in str(exc)
    else:
        raise AssertionError("Salesforce sem instância deveria falhar fechado")


def test_commercial_outcomes_do_not_invent_attribution_semantics():
    assert _outcome_bucket("WON") == "won"
    assert _outcome_bucket("MEETING_SCHEDULED") == "meeting"
    assert _outcome_bucket("RESPONDED") == "reply"
    assert _outcome_bucket("unknown") == "other"


class _Opportunity:
    signals_matched = ["NEW_FACTORY", {"signal": "HIRING_ENGINEER"}, {"other": "ignored"}]


def test_signal_parser_only_uses_explicit_matched_signals():
    assert _signals(_Opportunity()) == {"NEW_FACTORY", "HIRING_ENGINEER"}
