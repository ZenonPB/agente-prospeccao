"""Testes do módulo de forecast e oportunidade (roadmap-vendas 4.8)."""
from src.db.models import LostReason, LeadStatus
from src.services.analytics_service import STAGE_WIN_RATES


def test_lost_reason_enum_values():
    assert {r.value for r in LostReason} == {
        "PRECO",
        "PRAZO",
        "NAO_RESPONDEU",
        "CONCORRENTE",
        "OUTRO",
    }


def test_stage_win_rates_probabilities():
    assert STAGE_WIN_RATES[LeadStatus.NOVO] == 0.05
    assert STAGE_WIN_RATES[LeadStatus.QUALIFICADO] == 0.15
    assert STAGE_WIN_RATES[LeadStatus.CONTATADO] == 0.25
    assert STAGE_WIN_RATES[LeadStatus.RESPONDIDO] == 0.40
    assert STAGE_WIN_RATES[LeadStatus.REUNIAO_MARCADA] == 0.60
    assert STAGE_WIN_RATES[LeadStatus.PROPOSTA_ENVIADA] == 0.90
