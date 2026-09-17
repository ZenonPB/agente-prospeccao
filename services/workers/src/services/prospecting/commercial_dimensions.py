"""Dimensões comerciais derivadas do vetor existente, em shadow mode.

A Fase 1E não cria um segundo motor de scoring. Ela projeta o `score_vector`
canônico em quatro dimensões legíveis e calcula uma prioridade experimental.
O resultado é diagnóstico: não altera `qualification_score`, `priority`,
`overall`, ordenação, promoção ou qualquer decisão do funil.

UNKNOWN permanece UNKNOWN. Dimensões ausentes não recebem zero e não derrubam
outras dimensões conhecidas; em especial, baixa contatabilidade nunca reduz a
aderência.
"""
from __future__ import annotations

from typing import Any, Mapping

FORMULA_VERSION = "commercial-dimensions-shadow-v1"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0.0, min(100.0, float(value)))


def _weighted_known(vector: Mapping[str, Any], weights: Mapping[str, float]) -> int | None:
    known = [(key, _number(vector.get(key)), weight) for key, weight in weights.items()]
    observed = [(value, weight) for _, value, weight in known if value is not None and weight > 0]
    if not observed:
        return None
    denominator = sum(weight for _, weight in observed)
    return round(sum(value * weight for value, weight in observed) / denominator)


def _coverage_confidence(vector: Mapping[str, Any]) -> int | None:
    """Usa a cobertura já calculada pelo Opportunity Vector como proxy explícita.

    `coverage` é 0..1 no `opportunity-v2`. Não inferimos confiabilidade da fonte
    quando esse dado não existe; ausência permanece `None`.
    """
    raw = vector.get("coverage")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return round(max(0.0, min(1.0, float(raw))) * 100)


def derive_commercial_dimensions(score_vector: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Deriva Aderência/Momento/Contatabilidade/Confiança sem mudar ranking.

    Fontes são somente dimensões já persistidas no `score_vector`:
    - aderência: `icp_fit` + `commercial_fit`;
    - momento: `intent` + `timing`;
    - contatabilidade: `reachability`, com `contactability` e
      `decision_maker_accessibility` como sinais complementares legados;
    - confiança dos dados: `coverage` do Opportunity Vector.

    A prioridade shadow exige aderência conhecida. As demais dimensões entram
    com peso pequeno/moderado apenas quando observadas; pesos ausentes são
    renormalizados, portanto UNKNOWN nunca equivale a zero.
    """
    if not isinstance(score_vector, Mapping):
        return None

    adherence = _weighted_known(score_vector, {"icp_fit": 0.7, "commercial_fit": 0.3})
    moment = _weighted_known(score_vector, {"intent": 0.55, "timing": 0.45})
    contactability = _weighted_known(
        score_vector,
        {"reachability": 0.65, "contactability": 0.25, "decision_maker_accessibility": 0.10},
    )
    data_confidence = _coverage_confidence(score_vector)

    dimensions = {
        "adherence": adherence,
        "moment": moment,
        "contactability": contactability,
        "data_confidence": data_confidence,
    }
    priority_score: int | None = None
    priority_band = "UNKNOWN"
    if adherence is not None:
        priority_score = _weighted_known(
            dimensions,
            {"adherence": 0.50, "moment": 0.30, "contactability": 0.10, "data_confidence": 0.10},
        )
        if priority_score is not None:
            priority_band = "HIGH" if priority_score >= 75 else "MEDIUM" if priority_score >= 50 else "LOW"

    return {
        **dimensions,
        "priority_score": priority_score,
        "priority_band": priority_band,
        "formula_version": FORMULA_VERSION,
        "shadow": True,
        "sources": {
            "adherence": ["icp_fit", "commercial_fit"],
            "moment": ["intent", "timing"],
            "contactability": ["reachability", "contactability", "decision_maker_accessibility"],
            "data_confidence": ["coverage"],
        },
    }
