"""CNPJ canônico do Registry (Fase 1B).

Seam: `services.registry.cnpj` — normalize/is_valid/dv_ok.
Valores esperados vêm de CNPJs reais (Petrobras/Vale/Itaú/BB, via BrasilAPI)
e do primeiro CNPJ alfanumérico oficial (Receita, jul/2026: 00.000.000/E08G-12).
"""
from __future__ import annotations


def test_normalize_strips_mask_and_uppercases():
    from services.registry.cnpj import normalize_cnpj

    assert normalize_cnpj("33.000.167/0001-01") == "33000167000101"
    assert normalize_cnpj(" 33.000.167/0001-01 ") == "33000167000101"
    assert normalize_cnpj("00.000.000/E08G-12") == "00000000E08G12"


def test_normalize_is_none_safe():
    from services.registry.cnpj import normalize_cnpj

    assert normalize_cnpj(None) is None
    assert normalize_cnpj("") is None
    assert normalize_cnpj("   ") is None


def test_real_numeric_cnpjs_are_valid():
    from services.registry.cnpj import is_valid_cnpj

    assert is_valid_cnpj("33.000.167/0001-01") is True  # Petrobras
    assert is_valid_cnpj("33.592.510/0001-54") is True  # Vale
    assert is_valid_cnpj("60.701.190/0001-04") is True  # Itaú
    assert is_valid_cnpj("00.000.000/0001-91") is True  # Banco do Brasil


def test_wrong_check_digits_are_invalid():
    from services.registry.cnpj import is_valid_cnpj

    assert is_valid_cnpj("33.000.167/0001-02") is False
    assert is_valid_cnpj("33.000.167/0001-00") is False


def test_repeated_digits_are_invalid():
    from services.registry.cnpj import is_valid_cnpj

    assert is_valid_cnpj("00000000000000") is False
    assert is_valid_cnpj("11111111111111") is False


def test_wrong_length_and_garbage_are_invalid():
    from services.registry.cnpj import is_valid_cnpj

    assert is_valid_cnpj("3300016700010") is False
    assert is_valid_cnpj("330001670001011") is False
    assert is_valid_cnpj(None) is False
    assert is_valid_cnpj("") is False
    assert is_valid_cnpj("33.000.167/0001-0!") is False


def test_alphanumeric_cnpj_format_is_accepted_without_numeric_dv():
    """CNPJs alfanuméricos (Receita, a partir de jul/2026) passam no formato;
    a verificação de dígitos clássica só se aplica aos numéricos."""
    from services.registry.cnpj import is_valid_cnpj, numeric_dv_ok

    assert is_valid_cnpj("00.000.000/E08G-12") is True
    assert is_valid_cnpj("00000000E08G12") is True
    assert numeric_dv_ok("00000000E08G12") is False
    assert is_valid_cnpj("00.000.000/E08G-1") is False


def test_numeric_dv_check_matches_known_values():
    from services.registry.cnpj import numeric_dv_ok

    assert numeric_dv_ok("33000167000101") is True
    assert numeric_dv_ok("33000167000102") is False
