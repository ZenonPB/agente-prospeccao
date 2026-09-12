from types import SimpleNamespace

from src.services.data_health_service import DataHealthService


def test_phone_freshness_does_not_reuse_generic_person_timestamp():
    person = SimpleNamespace(
        phone="+5516999999999",
        last_verified_at="2026-09-12T10:00:00+00:00",
        raw_data={},
    )

    assert DataHealthService._phone_observed_at(person) is None


def test_phone_freshness_uses_phone_specific_observation():
    person = SimpleNamespace(
        phone="+5516999999999",
        last_verified_at="2026-09-12T10:00:00+00:00",
        raw_data={
            "phone_verification_history": [
                {"state": "LIKELY_VALID", "observed_at": "2026-09-10T10:00:00+00:00"},
            ],
        },
    )

    assert DataHealthService._phone_observed_at(person) == "2026-09-10T10:00:00+00:00"
