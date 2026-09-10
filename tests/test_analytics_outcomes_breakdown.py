"""Cortes de BI por dimensão sobre outcomes (P1.25).

Função pura `build_outcomes_breakdown`: agrupa outcomes por dimensão
(vertical, consultor, canal, campanha, provider, versão) com amostra sempre
visível. `None`/vazio vira bucket explícito "(sem ...)" — nunca descartado
silenciosamente.
"""


def test_breakdown_agrupa_por_dimensao_com_amostra_e_ticket():
    from src.services.analytics_service import build_outcomes_breakdown

    rows = [
        {"group": "industria", "outcome": "WON", "value": 1000.0},
        {"group": "industria", "outcome": "WON", "value": 3000.0},
        {"group": "industria", "outcome": "WON", "value": 2000.0},
        {"group": "industria", "outcome": "WON", "value": 2000.0},
        {"group": "industria", "outcome": "LOST", "value": 0.0},
        {"group": "industria", "outcome": "LOST", "value": 0.0},
        {"group": "servicos", "outcome": "LOST", "value": 0.0},
        {"group": "servicos", "outcome": "LOST", "value": 0.0},
    ]

    result = build_outcomes_breakdown(rows, by="vertical")

    assert result["by"] == "vertical"
    assert result["total_outcomes"] == 8
    assert result["sample_minimum"] == 5
    groups = {g["group"]: g for g in result["groups"]}
    industria = groups["industria"]
    assert industria["total"] == 6
    assert industria["won"] == 4
    assert industria["conversion_rate"] == round(4 / 6 * 100, 2)
    assert industria["average_ticket"] == 2000.0
    assert industria["sample_sufficient"] is True
    servicos = groups["servicos"]
    assert servicos["total"] == 2
    assert servicos["sample_sufficient"] is False


def test_breakdown_sem_dados_nao_confunde_vazio_com_zero():
    from src.services.analytics_service import build_outcomes_breakdown

    result = build_outcomes_breakdown([], by="canal")

    assert result["by"] == "canal"
    assert result["groups"] == []
    assert result["total_outcomes"] == 0


def test_breakdown_normaliza_grupo_vazio_em_bucket_explicito():
    from src.services.analytics_service import build_outcomes_breakdown

    result = build_outcomes_breakdown(
        [
            {"group": None, "outcome": "WON", "value": 500.0},
            {"group": "  ", "outcome": "LOST", "value": 0.0},
        ],
        by="vertical",
    )

    assert len(result["groups"]) == 1
    assert result["groups"][0]["group"] == "(sem vertical)"
    assert result["groups"][0]["total"] == 2
