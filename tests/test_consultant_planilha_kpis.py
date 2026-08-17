"""Testes dos KPIs da planilha Alphamec por consultor.

Cobre as funções puras:
- `compute_rate` (porcentagem com denominador zero);
- `mean` (média com lista vazia);
- `interval_days` (dias entre duas datas, naive/aware, mínimo 0);
- `build_planilha_kpis` (compactação dos KPIs em dict para a UI).
"""
from datetime import datetime, timedelta, timezone

from src.services.analytics_service import (
    build_planilha_kpis,
    compute_rate,
    interval_days,
    mean,
)


def test_compute_rate_normal():
    assert compute_rate(3, 10) == 30.0
    assert compute_rate(0, 10) == 0.0
    assert compute_rate(1, 3) == 33.3


def test_compute_rate_denominador_zero():
    assert compute_rate(5, 0) == 0.0


def test_mean_vazia_e_normal():
    assert mean([]) == 0.0
    assert mean([1, 2, 3, 4]) == 2.5


def test_interval_days():
    start = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 4, 9, 0, tzinfo=timezone.utc)
    assert interval_days(start, end) == 3
    # Naive vira UTC.
    naive = datetime(2026, 8, 4, 9, 0)
    assert interval_days(start, naive) == 3
    # Intervalo negativo é limitado a 0.
    assert interval_days(end, start) == 0
    # Falta de data → 0.
    assert interval_days(None, end) == 0
    assert interval_days(start, None) == 0


def test_interval_days_fracao_nao_conta_dia_parcial():
    """Menos de 24h não conta como dia (arredondamento para baixo)."""
    start = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=12)
    assert interval_days(start, end) == 0


def test_build_planilha_kpis_completo():
    kpis = build_planilha_kpis(
        assigned_leads=20,
        pitch_sent=10,
        responded_leads=5,
        contracts_approved=2,
        contracts_total=4,
        ticket_sum=8000.0,
        ticket_count=3,
        cadence_days=[2, 4, 6],
        close_days=[10, 20],
    )
    assert kpis["pitch_rate"] == 50.0            # 10/20
    assert kpis["response_rate"] == 50.0         # 5/10
    assert kpis["contract_approval_rate"] == 50.0  # 2/4
    assert kpis["ticket_medio"] == 2666.67       # 8000/3
    assert kpis["avg_cadence_days"] == 4.0       # (2+4+6)/3
    assert kpis["avg_close_days"] == 15.0        # (10+20)/2


def test_build_planilha_kpis_vazio():
    kpis = build_planilha_kpis(
        assigned_leads=0, pitch_sent=0, responded_leads=0,
        contracts_approved=0, contracts_total=0,
        ticket_sum=0, ticket_count=0,
        cadence_days=[], close_days=[],
    )
    assert kpis["pitch_rate"] == 0.0
    assert kpis["response_rate"] == 0.0
    assert kpis["contract_approval_rate"] == 0.0
    assert kpis["ticket_medio"] == 0.0
    assert kpis["avg_cadence_days"] == 0.0
    assert kpis["avg_close_days"] == 0.0