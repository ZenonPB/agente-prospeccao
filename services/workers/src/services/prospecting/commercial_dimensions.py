"""Dimensões comerciais derivadas da inteligência já existente, em shadow mode.

A Fase 1E não cria um segundo motor de scoring. Ela projeta o `score_vector`
canônico e evidências observadas em quatro dimensões legíveis e calcula uma
prioridade experimental. O resultado é diagnóstico: não altera
`qualification_score`, `priority`, `overall`, ordenação, promoção ou funil.

UNKNOWN permanece UNKNOWN. Dimensões ausentes não recebem zero e não derrubam
outras dimensões conhecidas; em especial, baixa contatabilidade nunca reduz a
aderência.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

FORMULA_VERSION = "commercial-dimensions-shadow-v1"


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        return None
    return max(0.0, min(100.0, numeric))


def _weighted_known(vector: Mapping[str, Any], weights: Mapping[str, float]) -> int | None:
    observed: list[tuple[float, float]] = []
    for key, weight in weights.items():
        value = _number(vector.get(key))
        if value is not None and weight > 0:
            observed.append((value, weight))
    if not observed:
        return None
    denominator = sum(weight for _, weight in observed)
    return round(sum(value * weight for value, weight in observed) / denominator)


def _data_confidence(
    vector: Mapping[str, Any], evidence: Iterable[Mapping[str, Any]] | None
) -> int | None:
    """Combina cobertura conhecida com confiança explícita das evidências."""
    coverage_raw = vector.get("coverage")
    coverage: float | None = None
    if not isinstance(coverage_raw, bool) and isinstance(coverage_raw, (int, float)):
        numeric = float(coverage_raw)
        if math.isfinite(numeric):
            coverage = max(0.0, min(1.0, numeric)) * 100.0

    confidences: list[float] = []
    for item in evidence or ():
        raw = item.get("confidence") if isinstance(item, Mapping) else None
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            continue
        numeric = float(raw)
        if not math.isfinite(numeric):
            continue
        confidences.append(max(0.0, min(100.0, numeric * 100.0 if numeric <= 1.0 else numeric)))

    evidence_confidence = sum(confidences) / len(confidences) if confidences else None
    if evidence_confidence is None:
        return round(coverage) if coverage is not None else None
    if coverage is None:
        return round(evidence_confidence)
    return round(evidence_confidence * 0.6 + coverage * 0.4)


def derive_commercial_dimensions(
    score_vector: Mapping[str, Any] | None,
    *,
    evidence: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Deriva Aderência/Momento/Contatabilidade/Confiança sem mudar ranking.

    Reutiliza apenas sinais já existentes. A prioridade shadow exige aderência
    conhecida; pesos UNKNOWN são renormalizados. Aderência e momento dominam a
    prioridade, enquanto contatabilidade orienta a próxima ação sem contaminar
    o fit da empresa.
    """
    if not isinstance(score_vector, Mapping):
        return None

    adherence = _weighted_known(
        score_vector,
        {"icp_fit": 0.65, "commercial_fit": 0.25, "buying_power": 0.10},
    )
    moment = _weighted_known(
        score_vector,
        {"intent": 0.45, "timing": 0.35, "need": 0.20},
    )
    contactability = _weighted_known(
        score_vector,
        {"reachability": 0.70, "contactability": 0.20, "decision_maker_accessibility": 0.10},
    )
    data_confidence = _data_confidence(score_vector, evidence)

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
            {"adherence": 0.55, "moment": 0.30, "contactability": 0.10, "data_confidence": 0.05},
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
            "adherence": ["icp_fit", "commercial_fit", "buying_power"],
            "moment": ["intent", "timing", "need"],
            "contactability": ["reachability", "contactability", "decision_maker_accessibility"],
            "data_confidence": ["evidence.confidence", "coverage"],
        },
    }
