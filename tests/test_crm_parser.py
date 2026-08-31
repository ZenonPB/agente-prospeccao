"""Testes do parser/normalizador do CRM Paste (funções puras, sem banco)."""
from datetime import date

from src.services.crm_service import (
    add_business_days,
    normalize_items,
    _norm_respondeu,
    _parse_date,
)


def test_add_business_days_pula_fim_de_semana():
    # Sexta-feira 31/07/2026 + 1 dia útil = segunda 03/08/2026.
    assert add_business_days(date(2026, 7, 31), 1) == date(2026, 8, 3)
    # Segunda 03/08/2026 + 4 dias úteis = sexta 07/08/2026.
    assert add_business_days(date(2026, 8, 3), 4) == date(2026, 8, 7)


def test_parse_date_aceita_formatos_brasileiros():
    assert _parse_date("03/08/2026") == date(2026, 8, 3)
    assert _parse_date("2026-08-03") == date(2026, 8, 3)
    assert _parse_date("") is None
    assert _parse_date("lixo") is None


def test_norm_respondeu():
    assert _norm_respondeu("SIM") == "SIM"
    assert _norm_respondeu("não") == "NÃO"
    assert _norm_respondeu("recusou") is None
    assert _norm_respondeu(None) is None


def test_normalize_defaults_followups_dias_uteis():
    itens = normalize_items(
        [{"lead": "Fabio Prada Perez", "empresa": "Clinica Maua", "pitch_enviado": True,
          "prospeccao": "2026-08-03"}],
        today=date(2026, 8, 3),
    )
    assert len(itens) == 1
    item = itens[0]
    # Sem pitch_data, usa a prospecção; follow-ups padrão em dias úteis.
    assert item["pitch_data"] == date(2026, 8, 3)
    assert item["follow_up_1"] == date(2026, 8, 7)   # +4 úteis
    assert item["follow_up_2"] == date(2026, 8, 12)  # +7 úteis
    assert item["follow_up_3"] == date(2026, 8, 17)  # +10 úteis


def test_normalize_descarta_item_sem_empresa():
    itens = normalize_items(
        [{"lead": "Sem empresa"}, {"lead": "Completo", "empresa": "ACME"}],
        today=date(2026, 8, 3),
    )
    assert [i["lead"] for i in itens] == ["Completo"]


def test_normalize_prospeccao_default_hoje():
    itens = normalize_items([{"lead": "Ana", "empresa": "Phoenix"}], today=date(2026, 8, 30))
    assert itens[0]["prospeccao"] == date(2026, 8, 30)
    assert itens[0]["pitch_enviado"] is False
