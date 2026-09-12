from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from services.prospecting.actionable_contact_score import calculate_actionable_contact_score


def test_actionable_score_explicitly_preserves_unknown_dimensions():
    person = SimpleNamespace(
        identity_confidence=80,
        role_label="Diretor de Engenharia",
        email=None,
        email_verified=False,
        phone=None,
        contact_confidence=70,
        last_verified_at=None,
        routability_type="UNKNOWN",
        routable=False,
        raw_data={},
    )

    result = calculate_actionable_contact_score(person)

    assert set(result["unknown_dimensions"]) == {
        "email_confidence",
        "phone_confidence",
        "freshness",
        "routability",
    }
    assert result["breakdown"]["email_confidence"]["state"] == "unknown"
    assert result["coverage"] < 1


def test_actionable_score_rewards_verified_reachable_recent_contact():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    person = SimpleNamespace(
        identity_confidence=95,
        role_label="Engineering Manager",
        email="ana@example.com",
        email_verified=True,
        phone="+5516999999999",
        contact_confidence=90,
        last_verified_at=now - timedelta(days=5),
        routability_type="DIRECT",
        routable=True,
        raw_data={"role_fit_score": 92},
    )

    result = calculate_actionable_contact_score(person, now=now)

    assert result["score"] >= 90
    assert result["status"] == "actionable"
    assert result["unknown_dimensions"] == []
    assert result["coverage"] == 1


def test_actionable_score_is_pure_and_deterministic():
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    person = {
        "identity_confidence": 70,
        "role_label": "CEO",
        "email": "ceo@example.com",
        "email_verified": False,
        "contact_confidence": 65,
        "phone": None,
        "last_verified_at": now - timedelta(days=45),
        "routability_type": "ROUTABLE",
        "routable": True,
        "raw_data": {},
    }

    assert calculate_actionable_contact_score(person, now=now) == calculate_actionable_contact_score(person, now=now)
