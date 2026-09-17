"""Métricas observacionais do piloto controlado do Data Engine Brasil.

O módulo é deliberadamente puro: recebe projeções já org-scoped e não faz I/O.
Não muda ranking, scoring, providers ou CRM. UNKNOWN permanece separado de zero.

`ready_for_review` mede se a telemetria técnica é suficiente para uma revisão.
`promotion_allowed` é mais estrito: exige também resultados comerciais reais e
atribuídos. Assim, cobertura sintética/diagnóstica nunca promove o shadow.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

DIMENSIONS = ("adherence", "moment", "contactability", "data_confidence")
POSITIVE_OUTCOMES = {"REPLY", "RESPONDED", "POSITIVE_REPLY", "MEETING", "MEETING_SCHEDULED", "MEETING_HELD", "WON", "CONVERTED", "SALE", "CLOSED_WON"}


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def summarize_pilot(
    leads: Iterable[Mapping[str, Any]],
    provider_metrics: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Resume cobertura, shadow-vs-legado, contatos, custo e outcomes observados."""
    lead_rows = list(leads)
    provider_rows = list(provider_metrics)
    outcome_rows = list(outcomes)
    total = len(lead_rows)

    dimension_known = {key: 0 for key in DIMENSIONS}
    shadow_known = 0
    divergence: list[float] = []
    contactable = 0
    qualified = 0

    for row in lead_rows:
        qualified += bool(row.get("qualified"))
        contactable += bool(row.get("contactable"))
        dimensions = row.get("commercial_dimensions")
        if not isinstance(dimensions, Mapping):
            continue
        shadow = _finite(dimensions.get("priority_score"))
        legacy = _finite(row.get("legacy_score"))
        if shadow is not None:
            shadow_known += 1
            if legacy is not None:
                divergence.append(abs(shadow - legacy))
        for key in DIMENSIONS:
            if _finite(dimensions.get(key)) is not None:
                dimension_known[key] += 1

    total_cost = 0.0
    provider_calls = 0
    provider_failures = 0
    provider_results = 0
    for metric in provider_rows:
        cost = _finite(metric.get("cost"))
        if cost is not None and cost > 0:
            total_cost += cost
        provider_calls += 1
        provider_results += max(0, int(_finite(metric.get("result_count")) or 0))
        provider_failures += str(metric.get("status") or "").lower() == "failed"

    attributed_outcomes = 0
    positive_outcomes = 0
    outcome_leads: set[str] = set()
    for outcome in outcome_rows:
        attributed = bool(outcome.get("attributed"))
        attributed_outcomes += attributed
        normalized = str(outcome.get("outcome") or "").strip().upper()
        if attributed and normalized in POSITIVE_OUTCOMES:
            positive_outcomes += 1
        lead_id = outcome.get("lead_id")
        if lead_id:
            outcome_leads.add(str(lead_id))

    def ratio(value: int) -> float | None:
        return round(value / total, 4) if total else None

    outcome_total = len(outcome_rows)
    return {
        "sample_size": total,
        "qualified": qualified,
        "contactable": contactable,
        "qualified_rate": ratio(qualified),
        "contactable_rate": ratio(contactable),
        "shadow_priority_coverage": ratio(shadow_known),
        "dimension_coverage": {key: ratio(value) for key, value in dimension_known.items()},
        "legacy_shadow_mean_absolute_delta": (
            round(sum(divergence) / len(divergence), 2) if divergence else None
        ),
        "legacy_shadow_comparable": len(divergence),
        "providers": {
            "executions": provider_calls,
            "failures": provider_failures,
            "results": provider_results,
            "failure_rate": round(provider_failures / provider_calls, 4) if provider_calls else None,
            "estimated_cost": round(total_cost, 6),
        },
        "outcomes": {
            "total": outcome_total,
            "attributed": attributed_outcomes,
            "positive": positive_outcomes,
            "worked_leads": len(outcome_leads),
            "attribution_rate": round(attributed_outcomes / outcome_total, 4) if outcome_total else None,
        },
    }


def evaluate_pilot_readiness(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Separa prontidão técnica de evidência suficiente para promoção.

    `ready_for_review` continua sendo um gate observacional. Promoção exige uma
    amostra realmente trabalhada, outcomes atribuídos e cobertura de todas as
    dimensões. Nenhum destes checks altera ranking automaticamente; a aplicação
    deve continuar em shadow até o contrato de promoção ser explicitamente
    adotado após o piloto.
    """
    sample = int(summary.get("sample_size") or 0)
    coverage = summary.get("dimension_coverage") if isinstance(summary.get("dimension_coverage"), Mapping) else {}
    provider_info = summary.get("providers") if isinstance(summary.get("providers"), Mapping) else {}
    outcome_info = summary.get("outcomes") if isinstance(summary.get("outcomes"), Mapping) else {}
    comparable = int(summary.get("legacy_shadow_comparable") or 0)

    review_checks = {
        "minimum_sample": sample >= 30,
        "shadow_comparison": comparable >= 20,
        "adherence_coverage": (_finite(coverage.get("adherence")) or 0) >= 0.80,
        "moment_coverage": (_finite(coverage.get("moment")) or 0) >= 0.60,
        "contactability_coverage": (_finite(coverage.get("contactability")) or 0) >= 0.60,
        "data_confidence_coverage": (_finite(coverage.get("data_confidence")) or 0) >= 0.80,
        "provider_failure_rate": (
            _finite(provider_info.get("failure_rate")) is not None
            and float(provider_info["failure_rate"]) <= 0.10
        ),
    }
    promotion_checks = {
        **review_checks,
        "worked_leads": int(outcome_info.get("worked_leads") or 0) >= 20,
        "attributed_outcomes": int(outcome_info.get("attributed") or 0) >= 10,
        "outcome_attribution_rate": (
            _finite(outcome_info.get("attribution_rate")) is not None
            and float(outcome_info["attribution_rate"]) >= 0.80
        ),
        "positive_outcomes_observed": int(outcome_info.get("positive") or 0) >= 1,
    }
    ready_for_review = all(review_checks.values())
    promotion_evidence_sufficient = all(promotion_checks.values())
    return {
        "ready_for_review": ready_for_review,
        "checks": review_checks,
        "promotion_evidence_sufficient": promotion_evidence_sufficient,
        "promotion_checks": promotion_checks,
        # Deliberadamente false: este módulo mede evidência, não muda política produtiva.
        "promotion_allowed": False,
        "note": (
            "Há evidência mínima para decidir uma promoção controlada; o shadow não é promovido automaticamente."
            if promotion_evidence_sufficient
            else "Shadow requer piloto real, outcomes atribuídos e revisão humana antes de alterar ranking."
        ),
    }
