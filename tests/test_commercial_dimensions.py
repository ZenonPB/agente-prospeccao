"""Fase 1E: dimensões comerciais são shadow, determinísticas e fail-unknown."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.prospecting.commercial_dimensions import (  # noqa: E402
    FORMULA_VERSION,
    derive_commercial_dimensions,
    shadow_derive_input,
)


def test_deriva_quatro_dimensoes_e_prioridade_sem_alterar_vetor():
    vector = {
        "icp_fit": 90,
        "commercial_fit": 70,
        "intent": 80,
        "timing": 60,
        "reachability": 40,
        "coverage": 0.75,
        "overall": 77,
        "formula_version": "opportunity-v2",
    }
    original = dict(vector)

    result = derive_commercial_dimensions(vector)

    assert vector == original
    assert result == {
        "adherence": 84,
        "moment": 71,
        "contactability": 40,
        "data_confidence": 75,
        "priority_score": 75,
        "priority_band": "HIGH",
        "formula_version": FORMULA_VERSION,
        "shadow": True,
        "sources": {
            "adherence": ["icp_fit", "commercial_fit", "buying_power"],
            "moment": ["intent", "timing", "need"],
            "contactability": ["reachability", "contactability", "decision_maker_accessibility"],
            "data_confidence": ["evidence.confidence", "coverage"],
        },
    }


def test_baixa_contatabilidade_nao_reduz_aderencia():
    high_contact = derive_commercial_dimensions({"icp_fit": 92, "commercial_fit": 88, "reachability": 100})
    low_contact = derive_commercial_dimensions({"icp_fit": 92, "commercial_fit": 88, "reachability": 0})

    assert high_contact["adherence"] == low_contact["adherence"] == 91
    assert high_contact["contactability"] == 100
    assert low_contact["contactability"] == 0


def test_unknown_nao_vira_zero_e_pesos_sao_renormalizados():
    result = derive_commercial_dimensions({"icp_fit": 80, "intent": 70})

    assert result["adherence"] == 80
    assert result["moment"] == 70
    assert result["contactability"] is None
    assert result["data_confidence"] is None
    assert result["priority_score"] == 76
    assert result["priority_band"] == "HIGH"


def test_sem_aderencia_nao_inventa_prioridade():
    result = derive_commercial_dimensions({"intent": 90, "timing": 90, "reachability": 100, "coverage": 1.0})

    assert result["adherence"] is None
    assert result["priority_score"] is None
    assert result["priority_band"] == "UNKNOWN"


def test_confianca_combina_evidencia_explicita_e_cobertura():
    result = derive_commercial_dimensions(
        {"icp_fit": 80, "coverage": 0.50},
        evidence=[{"confidence": 0.9}, {"confidence": 70}, {"confidence": None}],
    )

    # média das evidências = 80; 60% evidência + 40% cobertura(50) = 68.
    assert result["data_confidence"] == 68


def test_numeros_invalidos_nao_contornam_unknown():
    result = derive_commercial_dimensions({
        "icp_fit": 120,
        "commercial_fit": -10,
        "intent": True,
        "timing": 200,
        "reachability": False,
        "coverage": 2.5,
        "buying_power": math.nan,
    })

    assert result["adherence"] == 72
    assert result["moment"] == 100
    assert result["contactability"] is None
    assert result["data_confidence"] == 100


def test_input_ausente_permanece_ausente():
    assert derive_commercial_dimensions(None) is None


def test_shadow_sem_pontuacao_preserva_unknown():
    """Lead ainda não pontuado: zeros de fallback não viram medida."""
    vector = {
        "icp_fit": 0,
        "need": 0,
        "intent": None,
        "buying_power": None,
        "reachability": None,
        "timing": None,
        "commercial_fit": 0,
    }
    shadow = shadow_derive_input(
        {}, vector, qualification_observed=False, opportunity_observed=False
    )
    result = derive_commercial_dimensions(shadow)

    assert result["adherence"] is None
    assert result["moment"] is None
    assert result["priority_score"] is None
    assert result["priority_band"] == "UNKNOWN"


def test_shadow_com_pontuacao_real_mantem_zeros_observados():
    shadow = shadow_derive_input(
        {}, {"icp_fit": 0, "need": 0, "commercial_fit": 0},
        qualification_observed=True, opportunity_observed=False,
    )
    result = derive_commercial_dimensions(shadow)

    assert result["adherence"] == 0
    assert result["moment"] == 0
    assert result["priority_band"] == "LOW"


def test_shadow_mantem_chaves_do_vetor_existente():
    shadow = shadow_derive_input(
        {"icp_fit": 80}, {"icp_fit": 80, "need": 0, "commercial_fit": 0},
        qualification_observed=False, opportunity_observed=False,
    )

    assert shadow["icp_fit"] == 80
    assert "need" not in shadow
    assert "commercial_fit" not in shadow


def test_shadow_oportunidade_ampara_fit_mas_nao_need():
    shadow = shadow_derive_input(
        {}, {"icp_fit": 70, "need": 0, "commercial_fit": 65},
        qualification_observed=False, opportunity_observed=True,
    )

    assert shadow["icp_fit"] == 70
    assert shadow["commercial_fit"] == 65
    assert "need" not in shadow
