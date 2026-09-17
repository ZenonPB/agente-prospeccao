"""Métricas de fechamento da Fase 1 / piloto do Data Engine Brasil.

O módulo é deliberadamente puro: recebe projeções já org-scoped e não faz I/O.
Não muda ranking, scoring, providers ou CRM. UNKNOWN permanece separado de zero.
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

DIMENSIONS = ("adherence", "moment", "contactability", "data_confidence")


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def summarize_pilot(
    leads: Iterable[Mapping[str, Any]],
    provider_metrics: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Resume cobertura, shadow-vs-legado, contatos e custo sem inventar dados."""
    lead_rows = list(leads)
    provider_rows = list(provider_metrics)
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

    def ratio(value: int) -> float | None:
        return round(value / total, 4) if total else None

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
    }


def evaluate_pilot_readiness(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Avalia somente suficiência observacional; não promove o shadow automaticamente.

    Os checks são explícitos para impedir que ausência de amostra seja interpretada
    como sucesso. `ready_for_review` significa apenas que há dados mínimos para uma
    revisão humana; não significa que a fórmula está aprovada para produção.
    """
    sample = int(summary.get("sample_size") or 0)
    coverage = summary.get("dimension_coverage") if isinstance(summary.get("dimension_coverage"), Mapping) else {}
    provider_info = summary.get("providers") if isinstance(summary.get("providers"), Mapping) else {}
    comparable = int(summary.get("legacy_shadow_comparable") or 0)

    checks = {
        "minimum_sample": sample >= 30,
        "shadow_comparison": comparable >= 20,
        "adherence_coverage": (_finite(coverage.get("adherence")) or 0) >= 0.80,
        "moment_coverage": (_finite(coverage.get("moment")) or 0) >= 0.60,
        "data_confidence_coverage": (_finite(coverage.get("data_confidence")) or 0) >= 0.80,
        "provider_failure_rate": (
            _finite(provider_info.get("failure_rate")) is not None
            and float(provider_info["failure_rate"]) <= 0.10
        ),
    }
    return {
        "ready_for_review": all(checks.values()),
        "checks": checks,
        "promotion_allowed": False,
        "note": "Shadow requer revisão humana e resultados do piloto antes de alterar ranking.",
    }
