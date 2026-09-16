"""Targeting OfferProfile → Registry: filtros, gate anti-varredura e raio.

RED (TDD): cobre §7/§8 do plano — geografia só com o que o Registry suporta,
campanha sem CNAE nunca varre o universo, raio não vira município.
"""
from __future__ import annotations


def test_geography_states_vira_filtro_uf():
    from services.registry.targeting import build_search_filters

    filters = build_search_filters(
        {"cnaes": ["28"], "geography": {"country": "BR", "states": ["SP"]}},
    )
    assert filters is not None
    assert filters.uf == "SP"


def test_multiplos_states_nao_inventa_filtro():
    from services.registry.targeting import build_search_filters

    filters = build_search_filters(
        {"cnaes": ["28"], "geography": {"country": "BR", "states": ["SP", "RJ"]}},
    )
    # Registry só filtra 1 UF por busca; múltiplas UFs = sem filtro UF aqui
    # (o chamador pagina por UF) — nunca inventa município.
    assert filters is not None
    assert filters.uf is None
    assert filters.ufs == ["RJ", "SP"]
    assert filters.municipio_cod is None


def test_multiplos_states_aplicados_nao_sao_unapplied():
    from services.registry.targeting import TargetingResult

    result = TargetingResult.from_offer({
        "cnaes": ["28"],
        "geography": {"states": ["SP", "MG"]},
    })
    assert result.filters is not None
    assert result.filters.ufs == ["MG", "SP"]
    assert "multi_uf" not in result.unapplied


def test_campanha_sem_cnae_nao_varre_registry():
    from services.registry.targeting import build_search_filters

    assert build_search_filters({"geography": {"country": "BR"}}) is None
    assert build_search_filters({"cnaes": [], "geography": {"states": ["SP"]}}) is None
    assert build_search_filters({"cnaes": ["invalido!!!"]}) is None


def test_raio_nao_vira_municipio_silenciosamente():
    from services.registry.targeting import TargetingResult

    result = TargetingResult.from_offer(
        {"cnaes": ["28"], "geography": {"country": "BR", "radius_km": 50, "city": "Araraquara"}},
    )
    assert result.filters is not None
    assert result.filters.municipio_cod is None
    assert "radius" in result.unapplied


def test_cnae_prefixo_divisao_chega_ao_search():
    from services.registry.targeting import build_search_filters

    filters = build_search_filters({"cnaes": ["28", "8630-5/04"]}, {})
    assert filters is not None
    assert filters.cnae_prefixes == ["28"]
    assert filters.cnaes == ["8630504"]


def test_cnae_prefixo_com_zero_a_direita_preserva_granularidade():
    from services.registry.targeting import build_search_filters

    filters = build_search_filters({"cnaes": ["250"]})
    assert filters is not None
    assert filters.cnae_prefixes == ["250"]


def test_states_precisa_ser_lista_de_ufs():
    from services.registry.targeting import build_search_filters

    assert build_search_filters({"cnaes": ["28"], "geography": {"states": "SP"}}) is None
    assert build_search_filters({"cnaes": ["28"], "geography": {"states": ["S"]}}) is None


def test_ufs_validas_normalizam_lowercase_e_deduplicam():
    from services.registry.targeting import build_search_filters

    filters = build_search_filters({
        "cnaes": ["28"],
        "geography": {"states": [" sp ", "MG", "SP"]},
    })

    assert filters is not None
    assert filters.uf is None
    assert filters.ufs == ["MG", "SP"]


def test_uf_duplicada_colapsa_para_filtro_singular():
    from services.registry.targeting import build_search_filters

    filters = build_search_filters({
        "cnaes": ["28"],
        "geography": {"states": ["SP", "sp"]},
    })

    assert filters is not None
    assert filters.uf == "SP"
    assert filters.ufs is None


def test_uf_inexistente_nao_e_aplicada_silenciosamente():
    from services.registry.targeting import build_search_filters

    assert build_search_filters({"cnaes": ["28"], "geography": {"states": ["XX"]}}) is None


def test_ufs_malformadas_nao_sao_filtradas_silenciosamente():
    from services.registry.targeting import build_search_filters

    for states in ([""], ["   "], ["123"], ["SAO PAULO"], ["SP", "XX"]):
        assert build_search_filters({
            "cnaes": ["28"],
            "geography": {"states": states},
        }) is None


def test_target_candidates_vira_limit_sem_materializar_universo():
    from services.registry.targeting import build_search_filters

    filters = build_search_filters({"cnaes": ["28"]}, target_candidates=30)
    assert filters is not None
    assert filters.limit == 30


def test_company_sizes_e_situacao_declarados_viram_filtros_registry():
    from services.registry.targeting import build_search_filters

    filters = build_search_filters({
        "cnaes": ["28"],
        "company_sizes": ["ME", "EPP"],
        "geography": {
            "country": "BR",
            "states": ["SP"],
            "municipality_code": "7107",
            "situations": ["2"],
            "matrix": True,
        },
    })
    assert filters is not None
    assert filters.portes == ["01", "03"]
    assert filters.municipio_cod == "7107"
    assert filters.situacoes == ["2"]
    assert filters.matriz is True


def test_porte_desconhecido_nao_e_aplicado_silenciosamente():
    from services.registry.targeting import build_search_filters

    assert build_search_filters({"cnaes": ["28"], "company_sizes": ["gigante"]}) is None
