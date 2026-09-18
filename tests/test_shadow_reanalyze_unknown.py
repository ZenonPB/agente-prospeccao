"""Re-análise de lead não pontuado não pode fabricar medida zero.

Cenário: `DataIntelligenceService.analyze_lead` persiste o vetor com
fallbacks zero; numa segunda análise, esses zeros estão no
`existing_vector`. "Presente no vetor existente" não prova observação —
sem este teste, a segunda análise transforma Aderência UNKNOWN em 0/LOW.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

from services.prospecting.commercial_dimensions import (  # noqa: E402
    derive_commercial_dimensions,
    shadow_derive_input,
)


def test_reanalise_de_nao_pontuado_nao_fabrica_aderencia_zero():
    persisted = {
        "icp_fit": 0,
        "need": 0,
        "intent": None,
        "buying_power": None,
        "reachability": None,
        "timing": None,
        "commercial_fit": 0,
        "overall": 0,
        "coverage": 0.0,
        "formula_version": "opportunity-v2",
    }
    shadow = shadow_derive_input(
        persisted, dict(persisted),
        qualification_observed=False, opportunity_observed=False,
    )
    result = derive_commercial_dimensions(shadow)

    assert result["adherence"] is None
    assert result["moment"] is None
    assert result["priority_score"] is None
    assert result["priority_band"] == "UNKNOWN"
