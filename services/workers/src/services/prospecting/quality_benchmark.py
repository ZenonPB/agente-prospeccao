"""Benchmark de regressão da inteligência de prospecção.

Este benchmark NÃO mede conversão real da AlphaMec. Ele usa casos sintéticos e
anonimizados para impedir regressões arquiteturais: oferta errada no topo,
false-positive de alta confiança ou oportunidade forte sem evidência.

Métricas de negócio reais (resposta, reunião, contrato, precision@20 humana)
só podem ser calculadas a partir de campanhas/outcomes reais e permanecem fora
deste gate de CI.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable

from services.prospecting.default_profiles import build_default_registry
from services.prospecting.offer_matcher import OfferMatcher


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    expected_offer: str
    lead_data: dict[str, Any]
    should_be_high_confidence: bool
    description: str


@dataclass(frozen=True)
class BenchmarkCaseResult:
    case_id: str
    expected_offer: str
    top_offer: str | None
    expected_score: int
    confidence_band: str | None
    routed_correctly: bool
    high_confidence_expected: bool
    high_confidence_observed: bool
    evidence_count: int


ANCHOR_CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        "landing-local-demand",
        "landing_page",
        {
            "company_name": "Clínica Exemplo",
            "segment": "psicologia",
            "company_size": "ME",
            "no_own_website": True,
            "has_instagram": True,
            "has_ads": True,
            "weak_conversion_flow": True,
        },
        True,
        "Negócio local com aquisição digital e ausência de página de conversão.",
    ),
    BenchmarkCase(
        "systems-operational-pain",
        "web_systems_erp",
        {
            "company_name": "Distribuidora Exemplo",
            "segment": "distribuição",
            "company_size": "EPP",
            "manual_process": True,
            "uses_spreadsheets": True,
            "multi_unit": True,
            "expanding": True,
        },
        True,
        "Operação multiunidade sustentada por processo manual e planilhas.",
    ),
    BenchmarkCase(
        "mechanical-expansion",
        "mechanical_project",
        {
            "company_name": "Indústria Exemplo",
            "segment": "metalúrgica",
            "company_size": "EPP",
            "cnae": "25.11",
            "has_cnpj": True,
            "has_business_email": True,
            "has_phone": True,
            "has_production_line": True,
            "expanding_factory": True,
            "new_equipment": True,
        },
        True,
        "Indústria com linha produtiva, expansão e novo equipamento.",
    ),
    BenchmarkCase(
        "sports-awards",
        "trophies_sports",
        {
            "company_name": "Organizador Esportivo Exemplo",
            "segment": "campeonatos",
            "event_scheduled": True,
            "hosts_events": True,
            "seasonal_demand": True,
            "custom_products": True,
            "has_phone": True,
        },
        True,
        "Competição futura com organizador e sinal de premiação recorrente.",
    ),
    BenchmarkCase(
        "mej-awards",
        "trophies_mej",
        {
            "company_name": "Núcleo Exemplo",
            "segment": "MEJ",
            "event_scheduled": True,
            "hosts_events": True,
            "seasonal_demand": True,
            "custom_products": True,
            "has_instagram": True,
        },
        True,
        "Evento do Movimento Empresa Júnior com edição futura e recorrência.",
    ),
)


HARD_NEGATIVES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        "landing-robust-site-no-pain",
        "landing_page",
        {
            "company_name": "Empresa Digital Madura",
            "segment": "psicologia",
            "company_size": "ME",
            "has_own_website_institutional": True,
            "has_instagram": True,
        },
        False,
        "Presença digital existente sem evidência de problema de conversão.",
    ),
    BenchmarkCase(
        "systems-small-simple-operation",
        "web_systems_erp",
        {
            "company_name": "Operação Simples",
            "segment": "serviços",
            "company_size": "ME",
            "very_small_low_complexity": True,
            "has_business_email": True,
        },
        False,
        "Empresa existente, mas sem evidência de complexidade operacional.",
    ),
    BenchmarkCase(
        "mechanical-industrial-without-need",
        "mechanical_project",
        {
            "company_name": "Indústria Estável",
            "segment": "metalúrgica",
            "company_size": "EPP",
            "cnae": "25.11",
            "has_cnpj": True,
            "has_phone": True,
        },
        False,
        "Firmografia industrial sem evidência de projeto, expansão ou gargalo.",
    ),
    BenchmarkCase(
        "trophies-no-event",
        "trophies",
        {
            "company_name": "Empresa sem evento conhecido",
            "has_instagram": True,
            "has_phone": True,
        },
        False,
        "Contato disponível sem evento, recorrência ou demanda observada.",
    ),
)


def _case_result(matcher: OfferMatcher, case: BenchmarkCase) -> BenchmarkCaseResult:
    matches = matcher.match(case.lead_data, min_score=0)
    top = matches[0] if matches else None
    expected = next((item for item in matches if item.offer_key == case.expected_offer), None)
    score = expected.score if expected else 0
    band = str((expected.score_breakdown or {}).get("confidence_band")) if expected else None
    high = bool(expected and score >= 75 and band == "high")
    return BenchmarkCaseResult(
        case_id=case.case_id,
        expected_offer=case.expected_offer,
        top_offer=top.offer_key if top else None,
        expected_score=score,
        confidence_band=band,
        routed_correctly=bool(top and top.offer_key == case.expected_offer),
        high_confidence_expected=case.should_be_high_confidence,
        high_confidence_observed=high,
        evidence_count=len(expected.evidence) if expected else 0,
    )


def run_quality_benchmark(cases: Iterable[BenchmarkCase] | None = None) -> dict[str, Any]:
    """Executa o benchmark e devolve métricas estáveis para CI/documentação."""
    selected = tuple(cases) if cases is not None else (*ANCHOR_CASES, *HARD_NEGATIVES)
    matcher = OfferMatcher(build_default_registry())
    results = [_case_result(matcher, case) for case in selected]
    anchors = [item for item in results if item.high_confidence_expected]
    negatives = [item for item in results if not item.high_confidence_expected]

    routing_accuracy = (
        sum(item.routed_correctly for item in anchors) / len(anchors)
        if anchors else 1.0
    )
    high_confidence_recall = (
        sum(item.high_confidence_observed for item in anchors) / len(anchors)
        if anchors else 1.0
    )
    high_confidence_false_positive_rate = (
        sum(item.high_confidence_observed for item in negatives) / len(negatives)
        if negatives else 0.0
    )
    evidence_coverage = (
        sum(item.evidence_count > 0 for item in anchors) / len(anchors)
        if anchors else 1.0
    )
    return {
        "benchmark_kind": "synthetic_regression",
        "real_conversion_claim": False,
        "case_count": len(results),
        "routing_accuracy": round(routing_accuracy, 4),
        "high_confidence_recall": round(high_confidence_recall, 4),
        "high_confidence_false_positive_rate": round(high_confidence_false_positive_rate, 4),
        "evidence_coverage": round(evidence_coverage, 4),
        "results": [asdict(item) for item in results],
    }


def assert_release_quality(report: dict[str, Any] | None = None) -> None:
    """Gate de release do benchmark sintético.

    Valores são deliberadamente rígidos para os anchors conhecidos. Isso não
    substitui UAT nem precision@20 de campanhas reais.
    """
    report = report or run_quality_benchmark()
    failures: list[str] = []
    if report["routing_accuracy"] < 1.0:
        failures.append(f"routing_accuracy={report['routing_accuracy']:.2%} < 100%")
    if report["high_confidence_recall"] < 0.8:
        failures.append(f"high_confidence_recall={report['high_confidence_recall']:.2%} < 80%")
    if report["high_confidence_false_positive_rate"] > 0.0:
        failures.append(
            "high_confidence_false_positive_rate="
            f"{report['high_confidence_false_positive_rate']:.2%} > 0%"
        )
    if report["evidence_coverage"] < 1.0:
        failures.append(f"evidence_coverage={report['evidence_coverage']:.2%} < 100%")
    if failures:
        raise AssertionError("Benchmark de prospecção falhou: " + "; ".join(failures))
