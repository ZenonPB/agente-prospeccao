"""Testes das metas de vendas por consultor (roadmap-vendas 4.9)."""
from src.services.analytics_service import AnalyticsService


class FakeAnalyticsService(AnalyticsService):
    """Subclasse para testar a lógica sem banco real."""

    def __init__(self):
        pass


def test_target_month_usado_to_date():
    svc = FakeAnalyticsService()
    assert svc._target_month(from_date="2026-08-01", to_date="2026-09-15") == "2026-09"


def test_target_month_usado_from_date():
    svc = FakeAnalyticsService()
    assert svc._target_month(from_date="2026-07-01") == "2026-07"


def test_target_month_aceita_iso_sem_hora():
    svc = FakeAnalyticsService()
    assert svc._target_month(from_date="2026-08") == "2026-08"


def test_target_month_default_mes_atual():
    svc = FakeAnalyticsService()
    from datetime import datetime, timezone
    assert svc._target_month() == datetime.now(timezone.utc).strftime("%Y-%m")
