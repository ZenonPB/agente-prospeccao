from datetime import datetime, timedelta, timezone

from services.prospecting.freshness_policy import FreshnessState, evaluate_freshness
from services.prospecting.intent_engine import build_opportunity_vector, detect_technologies, extract_intent_signals, intent_score
from services.prospecting.intent_provider_registry import IntentProviderRegistry
from services.prospecting.phone_verification_service import PhoneVerificationState, verify_phone
from services.prospecting.technology_stack_provider import TechnologyStackProvider


def test_freshness_preserves_unknown():
    result = evaluate_freshness("email", None)
    assert result["state"] == FreshnessState.UNKNOWN.value
    assert result["age_days"] is None


def test_freshness_marks_expired_data_stale():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    result = evaluate_freshness("jobs", now - timedelta(days=15), now=now)
    assert result["state"] == FreshnessState.STALE.value
    assert result["ttl_days"] == 14


def test_phone_verification_is_conservative():
    assert verify_phone(None)["state"] == PhoneVerificationState.UNKNOWN.value
    assert verify_phone("11111111111")["state"] == PhoneVerificationState.INVALID.value
    mobile = verify_phone("(16) 99999-1234")
    assert mobile["state"] == PhoneVerificationState.LIKELY_VALID.value
    assert mobile["normalized"] == "+5516999991234"


def test_technographics_detects_known_stack_without_network():
    payload = {"html": "<script src='https://www.googletagmanager.com/gtag/js'></script><div class='wp-content'>"}
    names = {item["technology"] for item in detect_technologies(payload)}
    assert "WordPress" in names
    assert "Google Analytics" in names


def test_technology_provider_is_free_and_distinguishes_empty_from_success():
    provider = TechnologyStackProvider()
    empty = provider.detect({"html": "<main>site simples</main>"})
    detected = provider.detect({"html": "<div class='wp-content'>"})
    assert empty["status"] == "empty"
    assert empty["cost_units"] == 0
    assert detected["status"] == "success"
    assert detected["cost_units"] == 0


def test_intent_v2_combines_confidence_reliability_and_recency():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    evidence = [
        {
            "title": "Empresa anuncia nova fábrica e vagas para engenheiro mecânico",
            "source": "company_news",
            "confidence": 0.9,
            "observed_at": now.isoformat(),
        },
        {
            "title": "Edital para aquisição de software",
            "source": "pncp",
            "confidence": 0.95,
            "observed_at": now.isoformat(),
        },
    ]
    signals = extract_intent_signals(evidence, now=now)
    keys = {item["signal"] for item in signals}
    assert "NEW_FACTORY" in keys
    assert "HIRING_MECHANICAL_ENGINEER" in keys
    assert "SOFTWARE_PROCUREMENT" in keys
    assert 0 < intent_score(signals) <= 100


def test_intent_registry_exposes_provider_states_without_hidden_io():
    registry = IntentProviderRegistry()
    result = registry.run([
        {"source": "pncp", "title": "Edital para aquisição de software", "confidence": 0.9},
        {"source": "company_news", "title": "Nova fábrica anunciada", "confidence": 0.8},
    ])
    statuses = {item["provider"]: item["status"] for item in result["providers"]}
    assert statuses["procurement"] == "success"
    assert statuses["company_news"] == "success"
    assert statuses["job_postings"] == "empty"
    assert statuses["social"] == "empty"
    assert statuses["events"] == "empty"


def test_opportunity_vector_does_not_treat_unknown_as_zero_dimension():
    vector = build_opportunity_vector(
        icp_fit=90,
        need=80,
        intent=None,
        buying_power=None,
        reachability=70,
        timing=85,
    )
    assert vector["intent"] is None
    assert vector["coverage"] < 1
    assert vector["overall"] > 0
    assert vector["formula_version"] == "opportunity-v2"
