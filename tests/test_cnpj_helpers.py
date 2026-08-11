"""Testes de helpers de CNPJ — máscara de CPF (minimização), papel, confiança (4.7)."""
from services.cnpj_service import (
    _calculate_confidence,
    _map_qualification_to_role,
    is_valid_cnpj,
    mask_cpf,
)


def test_is_valid_cnpj():
    assert is_valid_cnpj("12.345.678/0001-95")
    assert not is_valid_cnpj("12345678")  # formato inválido (curto)


def test_mask_cpf_minimiza_dados():
    assert mask_cpf("123.456.789-00") == "123.***.***-00"
    assert mask_cpf("12345678900") == "123.***.***-00"
    assert mask_cpf(None) is None
    assert mask_cpf("1234") is None  # CPF inválido


def test_map_qualification_to_role():
    assert _map_qualification_to_role("Presidente") == "CEO"
    assert _map_qualification_to_role("Diretor Comercial") == "DIRETOR"
    assert _map_qualification_to_role("Administrador") == "ADMINISTRADOR"
    assert _map_qualification_to_role("Sócio Capitalista") == "SOCIO"
    assert _map_qualification_to_role("Qualquer coisa") == "OUTRO"


def test_calculate_confidence():
    assert _calculate_confidence("CEO", has_email=False) == 90
    assert _calculate_confidence("SOCIO", has_email=False) == 70
    assert _calculate_confidence("CEO", has_email=True) == 95
