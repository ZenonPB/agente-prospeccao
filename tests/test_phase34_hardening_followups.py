from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

from services.email_verification_service import EmailVerificationService
from services.prospecting.contact_verifier import ContactVerifier
from services.prospecting.employment_history_service import EmploymentHistoryService
from services.prospecting.external_intent_feed_provider import (
    ExternalIntentFeedProvider,
    validate_external_endpoint,
)
from services.prospecting.intent_engine import extract_intent_signals


UTC = timezone.utc


def _person(**kwargs):
    defaults = {
        "raw_data": {},
        "email": "decisor@example.com",
        "source": "company_site",
        "email_verified": False,
        "verification_status": "needs_review",
        "email_verified_at": None,
        "last_verified_at": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_employment_history_first_observation_is_not_a_change():
    person = _person()
    result = EmploymentHistoryService.observe(
        person,
        {"company_name": "Alpha Ltda", "title": "Diretor", "source": "job_postings"},
        observed_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    assert result["changed"] is False
    assert len(person.raw_data["employment_history"]) == 1
    assert person.raw_data["current_employment"]["company_name"] == "Alpha Ltda"


def test_employment_history_is_idempotent_for_same_company_and_role():
    person = _person()
    first = datetime(2026, 9, 1, tzinfo=UTC)
    second = first + timedelta(days=2)
    payload = {"company_name": "Alpha Ltda", "title": "Diretor", "source": "job_postings"}
    EmploymentHistoryService.observe(person, payload, observed_at=first)
    result = EmploymentHistoryService.observe(person, payload, observed_at=second)
    assert result["changed"] is False
    assert len(person.raw_data["employment_history"]) == 1
    assert person.raw_data["current_employment"]["last_seen_at"] == second.isoformat()


def test_employer_change_preserves_previous_snapshot_and_emits_intent():
    person = _person()
    EmploymentHistoryService.observe(
        person,
        {"company_name": "Alpha Ltda", "title": "Diretor", "source": "job_postings"},
        observed_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    result = EmploymentHistoryService.observe(
        person,
        {"company_name": "Beta SA", "title": "Diretor", "source": "job_postings", "confidence": 0.9},
        observed_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    assert result["changed"] is True
    assert result["change"]["change_type"] == "employer_changed"
    assert person.raw_data["employment_history"][0]["ended_at"] is not None
    assert person.raw_data["current_employment"]["company_name"] == "Beta SA"
    evidence = EmploymentHistoryService.latest_change_evidence(person)
    signals = extract_intent_signals([evidence])
    assert {item["signal"] for item in signals} == {"JOB_CHANGE"}


def test_role_change_is_distinct_from_employer_change():
    person = _person()
    EmploymentHistoryService.observe(person, {"company_name": "Alpha", "title": "Gerente"})
    result = EmploymentHistoryService.observe(person, {"company_name": "Alpha", "title": "Diretor"})
    assert result["change"]["change_type"] == "role_changed"


def _mx_domain_result():
    return {
        "verified": False,
        "domain_valid": True,
        "mx": "10 mx.example.com.",
        "reason": "mx_present",
    }


def test_email_v2_keeps_mx_only_as_domain_validated(monkeypatch):
    async def scenario():
        service = EmailVerificationService()

        async def base(_email, client=None):
            return _mx_domain_result()

        monkeypatch.setattr(service, "verify_email", base)
        result = await service.verify_email_v2("user@example.com")
        assert result["status"] == "domain_validated"
        assert result["verified"] is False
        assert result["auto_send_eligible"] is False

    asyncio.run(scenario())


def test_email_v2_detects_catchall_and_blocks_auto_send(monkeypatch):
    async def scenario():
        service = EmailVerificationService()

        async def base(_email, client=None):
            return _mx_domain_result()

        async def probe(_domain, _mx, enable_catchall_probe=False):
            assert enable_catchall_probe is True
            return {"is_catchall": True, "probed": True}

        monkeypatch.setattr(service, "verify_email", base)
        monkeypatch.setattr(service, "probe_smtp_catchall", probe)
        result = await service.verify_email_v2("user@example.com", enable_catchall_probe=True)
        assert result["status"] == "catch_all"
        assert result["verified"] is False
        assert result["auto_send_eligible"] is False

    asyncio.run(scenario())


def test_email_v2_non_catchall_does_not_prove_mailbox(monkeypatch):
    async def scenario():
        service = EmailVerificationService()

        async def base(_email, client=None):
            return _mx_domain_result()

        async def probe(_domain, _mx, enable_catchall_probe=False):
            return {"is_catchall": False, "probed": True}

        monkeypatch.setattr(service, "verify_email", base)
        monkeypatch.setattr(service, "probe_smtp_catchall", probe)
        result = await service.verify_email_v2("user@example.com", enable_catchall_probe=True)
        assert result["status"] == "non_catch_all"
        assert result["verified"] is False
        assert result["auto_send_eligible"] is False

    asyncio.run(scenario())


def test_contact_verifier_persists_bounded_history():
    class Service:
        async def verify_email_v2(self, email, enable_catchall_probe=False):
            return {
                "verified": False,
                "status": "domain_validated",
                "confidence": 65,
                "catch_all": None,
                "mx": "mx.example.com",
                "reason": "mx_valid_catchall_not_checked",
                "auto_send_eligible": False,
            }

    async def scenario():
        person = _person()
        verifier = ContactVerifier(Service())
        for _ in range(35):
            await verifier.verify_email(person)
        history = person.raw_data["email_verification_history"]
        assert len(history) == 1
        assert history[-1]["status"] == "domain_validated"
        assert ContactVerifier.latest_verified_at(person) is not None

    asyncio.run(scenario())


def test_passive_observation_does_not_erase_authoritative_mailbox_verification():
    class Service:
        async def verify_email_v2(self, email, enable_catchall_probe=False):
            return {
                "verified": False,
                "status": "non_catch_all",
                "confidence": 75,
                "catch_all": False,
                "mx": "mx.example.com",
                "reason": "mx_valid_non_catch_all_mailbox_unconfirmed",
                "auto_send_eligible": False,
            }

    async def scenario():
        verified_at = datetime(2026, 9, 10, tzinfo=UTC)
        person = _person(
            email_verified=True,
            verification_status="provider_verified",
            email_verified_at=verified_at,
        )
        result = await ContactVerifier(Service()).verify_email(person)
        assert result["email_verified"] is True
        assert result["passive_observation"] is True
        assert ContactVerifier.has_authoritative_verification(person) is True

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/feed",
        "https://localhost/feed",
        "https://127.0.0.1/feed",
        "https://169.254.169.254/latest",
        "https://[::1]/feed",
        "https://user:pass@example.com/feed",
        "https://example.com/feed#fragment",
    ],
)
def test_external_intent_provider_rejects_unsafe_destinations(url):
    assert validate_external_endpoint(url)[0] is False


def test_external_intent_provider_rejects_mixed_dns_resolution():
    assert validate_external_endpoint(
        "https://example.com/feed",
        resolved_ips=["93.184.216.34", "10.0.0.1"],
    )[0] is False


def test_external_intent_provider_normalizes_real_feed_contract(monkeypatch):
    async def scenario():
        provider = ExternalIntentFeedProvider(name="company_news", endpoint="https://feed.example.com/v1")

        async def safe():
            return True, "ok"

        monkeypatch.setattr(provider, "_destination_is_safe", safe)

        def handler(request: httpx.Request):
            return httpx.Response(
                200,
                json={"items": [{"id": "n-1", "title": "Empresa anuncia expansão", "published_at": "2026-09-12T00:00:00Z"}]},
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await provider.collect({"company": {"name": "Acme"}}, client=client)
        assert result.status == "success"
        assert result.evidence[0]["source"] == "company_news"
        assert result.evidence[0]["external_id"] == "n-1"

    asyncio.run(scenario())


def test_continuous_watch_is_noop_without_explicit_org_opt_in():
    async def scenario():
        from src.services.continuous_intelligence_service import ContinuousIntelligenceService

        org = SimpleNamespace(id="org-1", api_quota={})
        service = ContinuousIntelligenceService(SimpleNamespace())
        result = await service.run_once_for_org(org, force=True)
        assert result == {
            "organization_id": "org-1",
            "status": "disabled",
            "processed": 0,
            "changed": 0,
        }

    asyncio.run(scenario())
