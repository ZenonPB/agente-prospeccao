from services.prospecting.pilot_metrics import evaluate_pilot_readiness, summarize_pilot


def test_summary_preserva_unknown_e_nao_confunde_zero():
    summary = summarize_pilot(
        [
            {
                "legacy_score": 80,
                "qualified": True,
                "contactable": False,
                "commercial_dimensions": {
                    "adherence": 90,
                    "moment": None,
                    "contactability": 0,
                    "data_confidence": 85,
                    "priority_score": 82,
                },
            },
            {
                "legacy_score": 0,
                "qualified": False,
                "contactable": True,
                "commercial_dimensions": None,
            },
        ],
        [{"status": "success", "result_count": 3, "cost": 0.0}],
    )

    assert summary["sample_size"] == 2
    assert summary["qualified_rate"] == 0.5
    assert summary["contactable_rate"] == 0.5
    assert summary["dimension_coverage"]["adherence"] == 0.5
    assert summary["dimension_coverage"]["moment"] == 0.0
    assert summary["dimension_coverage"]["contactability"] == 0.5
    assert summary["legacy_shadow_mean_absolute_delta"] == 2.0
    assert summary["providers"]["estimated_cost"] == 0.0


def test_summary_sem_amostra_retorna_taxas_unknown():
    summary = summarize_pilot([], [])

    assert summary["sample_size"] == 0
    assert summary["qualified_rate"] is None
    assert summary["shadow_priority_coverage"] is None
    assert summary["legacy_shadow_mean_absolute_delta"] is None
    assert all(value is None for value in summary["dimension_coverage"].values())
    assert summary["providers"]["failure_rate"] is None


def test_provider_failure_e_custo_sao_agregados_sem_pii():
    summary = summarize_pilot(
        [],
        [
            {"provider": "public_web", "status": "success", "result_count": 4, "cost": 0},
            {"provider": "hunter", "status": "failed", "result_count": 0, "cost": 0.02},
        ],
    )

    assert summary["providers"] == {
        "executions": 2,
        "failures": 1,
        "results": 4,
        "failure_rate": 0.5,
        "estimated_cost": 0.02,
    }


def test_readiness_nunca_promove_shadow_automaticamente():
    summary = {
        "sample_size": 30,
        "legacy_shadow_comparable": 30,
        "dimension_coverage": {
            "adherence": 0.95,
            "moment": 0.8,
            "contactability": 0.5,
            "data_confidence": 0.9,
        },
        "providers": {"failure_rate": 0.05},
    }

    readiness = evaluate_pilot_readiness(summary)

    assert readiness["ready_for_review"] is True
    assert readiness["promotion_allowed"] is False


def test_readiness_falha_fechado_sem_dados_de_provider():
    readiness = evaluate_pilot_readiness({
        "sample_size": 100,
        "legacy_shadow_comparable": 100,
        "dimension_coverage": {"adherence": 1, "moment": 1, "data_confidence": 1},
        "providers": {},
    })

    assert readiness["ready_for_review"] is False
    assert readiness["checks"]["provider_failure_rate"] is False
