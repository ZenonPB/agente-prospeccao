"""Matching de CNAE do Registry: exato vs prefixo, principal vs secundário.

RED (TDD): estes testes devem FALHAR antes da implementação de
`services/registry/cnae_matching.py` existir com esta semântica.
"""
from __future__ import annotations

import pytest


def test_cnae_completo_numerico_vira_match_exato():
    from services.registry.cnae_matching import parse_cnae_tokens

    filt = parse_cnae_tokens(["8630504"])
    assert filt.exact == ("8630504",)
    assert filt.prefixes == ()


def test_cnae_completo_formatado_normaliza_para_exato():
    from services.registry.cnae_matching import parse_cnae_tokens

    filt = parse_cnae_tokens(["8630-5/04"])
    assert filt.exact == ("8630504",)
    assert filt.prefixes == ()


def test_prefixo_divisao_vira_faixa_ancorada():
    from services.registry.cnae_matching import parse_cnae_tokens

    filt = parse_cnae_tokens(["28"])
    assert filt.exact == ()
    assert filt.prefixes == (("2800000", "2899999"),)


def test_prefixo_nao_captura_divisao_errada():
    from services.registry.cnae_matching import parse_cnae_tokens

    filt = parse_cnae_tokens(["28"])
    (start, end) = filt.prefixes[0]
    assert not (start <= "2599999" <= end)
    assert not (start <= "3300000" <= end)
    assert start <= "2800000" <= end
    assert start <= "2869100" <= end


def test_multiplos_tokens_misturam_exato_e_prefixo_com_dedup():
    from services.registry.cnae_matching import parse_cnae_tokens

    filt = parse_cnae_tokens(["25", "28", "8630-5/04", "28", "8630504"])
    assert filt.exact == ("8630504",)
    assert filt.prefixes == (("2500000", "2599999"), ("2800000", "2899999"))


def test_entrada_invalida_falha_fechado():
    from services.registry.cnae_matching import parse_cnae_tokens

    with pytest.raises(ValueError):
        parse_cnae_tokens([""])
    with pytest.raises(ValueError):
        parse_cnae_tokens(["abc"])
    with pytest.raises(ValueError):
        parse_cnae_tokens(["12345678"])
    with pytest.raises(ValueError):
        parse_cnae_tokens(["abc28"])


def test_search_filters_rejeita_cnae_prefixo_invalido_sem_sanitizar():
    from services.registry.search import SearchFilters

    with pytest.raises(ValueError):
        SearchFilters(cnae_prefixes=["abc28"])
    with pytest.raises(ValueError):
        SearchFilters(cnae_prefixes=[""])
    with pytest.raises(ValueError):
        SearchFilters(cnae_prefixes=["1"])


def test_search_filters_aceita_prefixos_e_exatos_canonicos():
    from services.registry.search import SearchFilters

    filters = SearchFilters(cnae_prefixes=["28", "25", "28"], cnaes=["8630504"])
    assert filters.cnae_prefixes == ["25", "28"]
    assert filters.cnaes == ["8630504"]


def test_search_filters_rejeita_uf_invalida_sem_sanitizar():
    from services.registry.search import SearchFilters

    with pytest.raises(ValueError):
        SearchFilters(ufs=["SP", "XX"])
    with pytest.raises(ValueError):
        SearchFilters(ufs=["   "])


def test_sem_tokens_filtro_vazio_explicito():
    from services.registry.cnae_matching import parse_cnae_tokens

    assert parse_cnae_tokens([]).empty is True
    assert parse_cnae_tokens(None).empty is True
