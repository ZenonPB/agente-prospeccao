"""Testes do router de template — overlap de tokens."""
from services.template_router import token_overlap


def test_overlap_total():
    assert token_overlap("marketing digital", "marketing digital") == 1.0


def test_overlap_parcial():
    # "marketing digital para academias" vs "marketing digital" → tokens de a
    # presentes em b = 2/2 (b está contido). Simétrico: esperado alto.
    assert token_overlap("marketing digital para academias", "marketing digital") >= 0.5


def test_sem_overlap():
    assert token_overlap("engenharia mecânica", "landing pages") == 0.0


def test_acentos_normalizados():
    assert token_overlap("psicologia", "psicologia") == 1.0


def test_vazio():
    assert token_overlap("", "marketing") == 0.0
