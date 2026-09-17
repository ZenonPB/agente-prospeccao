from services.prospecting.contactability import assess_contactability


def test_unknown_when_not_observed():
    result = assess_contactability([])
    assert result["score"] is None
    assert result["status"] == "UNKNOWN"


def test_provider_failure_is_not_no_contact():
    result = assess_contactability([], discovery_status="failed")
    assert result["score"] is None
    assert result["status"] == "UNKNOWN"
    assert result["reason"] == "people_discovery_failed"


def test_completed_empty_is_observed_zero():
    result = assess_contactability([], discovery_status="empty")
    assert result["score"] == 0
    assert result["status"] == "NO_CONTACT_FOUND"


def test_verified_direct_person_is_high_contactability():
    result = assess_contactability([{
        "name": "Maria Silva",
        "email": "maria@example.com",
        "email_verified": True,
        "contact_confidence": 91,
        "raw_data": {"role_fit_score": 88},
    }])
    assert result["score"] >= 90
    assert result["status"] == "VERIFIED_DIRECT"
    assert result["verified_contact"] is True


def test_generic_company_channel_does_not_impersonate_decision_maker():
    result = assess_contactability([{
        "name": "Decisor",
        "email": "contato@example.com",
        "confidence": 69,
    }])
    assert result["status"] == "GENERIC_CHANNEL"
    assert result["person_found"] is False
    assert result["score"] <= 55


def test_person_without_channel_is_distinct_from_not_found():
    result = assess_contactability([{
        "name": "Joao Pereira",
        "confidence": 60,
        "raw_data": {"role_fit_score": 90},
    }])
    assert result["status"] == "PERSON_NO_CONTACT"
    assert result["person_found"] is True
    assert result["direct_contact"] is False


def test_best_contact_wins_without_averaging_away_a_good_decision_maker():
    result = assess_contactability([
        {"name": "Decisor", "email": "contato@example.com", "confidence": 55},
        {
            "name": "Ana Souza",
            "phone": "16999999999",
            "routable": True,
            "contact_confidence": 82,
            "raw_data": {"role_fit_score": 95},
        },
    ])
    assert result["status"] == "DIRECT"
    assert result["score"] >= 85
