"""Testes do módulo de SLA / leads parados (roadmap-vendas 4.10)."""
from datetime import datetime, timedelta, timezone

from src.services.sla_service import _days_since, _alert


def test_days_since_zero():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    anchor = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)
    assert _days_since(anchor, now) == 0


def test_days_since_naive_anchor():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    anchor = datetime(2026, 8, 5, 12, 0)  # sem tzinfo
    assert _days_since(anchor, now) == 5


def test_alert_structure():
    class FakeLead:
        id = "abc"
        company_name = "Empresa Teste"
        city = "Araraquara"
        state = "SP"
        status = type("S", (), {"value": "QUALIFICADO"})()
        qualification_score = 75
        assigned_to = None
        last_contacted_at = None
        next_action_at = None

    alert = _alert(
        FakeLead(), "QUALIFICADO_NO_CONTACT",
        "Apto sem contato há 6 dia(s)", 6,
    )
    assert alert["alert_type"] == "QUALIFICADO_NO_CONTACT"
    assert alert["company_name"] == "Empresa Teste"
    assert alert["days_since"] == 6
    assert alert["status"] == "QUALIFICADO"
    assert alert["last_contacted_at"] is None