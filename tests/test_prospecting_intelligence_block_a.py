"""Regressões do Bloco A — Prospecting Intelligence + Golden Paths."""
from __future__ import annotations

from datetime import date, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


def test_offer_resolver_distingue_principais_golden_paths():
    from services.prospecting.default_profiles import build_default_registry
    from services.prospecting.offer_profile import OfferProfileResolver

    resolver = OfferProfileResolver(build_default_registry())
    cases = {
        "landing pages para clínicas de psicologia": "landing_page",
        "sistemas web sob medida para empresas com processos manuais e planilhas": "web_systems_erp",
        "projeto mecânico para metalúrgicas e linhas de produção": "mechanical_project",
        "troféus para campeonatos, corridas e eventos esportivos": "trophies_sports",
        "troféus para eventos do MEJ e empresas juniores": "trophies_mej",
    }
    for text, expected in cases.items():
        resolved = resolver.resolve_campaign(target_service=text, target_segment=text)
        assert resolved.key == expected, (text, resolved.key, expected)


def test_quality_gate_nao_trata_unknown_como_false():
    from services.prospecting.default_profiles import build_default_registry
    from services.prospecting.offer_matcher import OfferMatcher

    matcher = OfferMatcher(build_default_registry())
    matches = {item.offer_key: item for item in matcher.match({
        "company_name": "Indústria sem dor observada",
        "segment": "metalúrgica",
        "company_size": "EPP",
        "cnae": "25.11",
        "has_cnpj": True,
        "has_phone": True,
    })}
    mechanical = matches["mechanical_project"]
    assert mechanical.score <= 55
    assert "missing_strong_evidence" in mechanical.score_breakdown["capped_by"]
    # O motor limita confiança; ele não fabrica sinais negativos ausentes.
    assert mechanical.score_breakdown["negative_signals_matched"] == []


def test_negative_penalty_so_existe_quando_sinal_foi_observado():
    from services.prospecting.default_profiles import build_default_registry
    from services.prospecting.offer_matcher import OfferMatcher

    matcher = OfferMatcher(build_default_registry())
    base = {
        "company_name": "Operação",
        "segment": "serviços",
        "company_size": "ME",
        "manual_process": True,
        "uses_spreadsheets": True,
    }
    clean = {item.offer_key: item for item in matcher.match(base)}["web_systems_erp"]
    negative = {item.offer_key: item for item in matcher.match({**base, "very_small_low_complexity": True})}["web_systems_erp"]
    assert clean.score_breakdown["negative_penalty"] == 0
    assert negative.score_breakdown["negative_penalty"] == 30
    assert negative.score < clean.score


def test_event_intelligence_reconhece_mej_sem_promover_inferencia_a_fato():
    from services.prospecting.event_intelligence import infer_event_intelligence

    result = infer_event_intelligence({
        "name": "Encontro de Empresas Juniores 2027",
        "organizer": "Núcleo Exemplo de Empresas Juniores",
        "event_type": "evento universitário",
    })
    assert result.context == "mej"
    assert result.recommended_offer_key == "trophies_mej"
    assert result.series_key
    assert result.evidence
    assert all(item["epistemic"] == "INFERENCE" for item in result.evidence)
    assert result.award_demand["epistemic"] == "INFERENCE"


def test_event_intelligence_reconhece_esporte_e_serie_entre_edicoes():
    from services.prospecting.event_intelligence import canonical_event_series_key, infer_event_intelligence

    result = infer_event_intelligence({
        "name": "12ª Copa Regional de Vôlei 2027",
        "organizer": "Liga Regional",
        "event_type": "campeonato",
    })
    assert result.context == "sports"
    assert result.recommended_offer_key == "trophies_sports"
    assert canonical_event_series_key("Copa Regional 2026", "Liga Regional", "campeonato") == canonical_event_series_key(
        "Copa Regional 2027", "Liga Regional", "campeonato"
    )


def test_estimativa_de_premiacao_exige_contagem_estruturada_e_permanece_inferencia():
    from services.prospecting.event_intelligence import infer_event_intelligence

    unknown = infer_event_intelligence({"name": "Feira empresarial", "organizer": "Associação X"})
    assert unknown.award_demand["estimated_min_units"] is None

    estimated = infer_event_intelligence({
        "name": "Campeonato Universitário",
        "organizer": "Liga Universitária",
        "category_count": 8,
        "placements_per_category": 3,
    })
    assert estimated.award_demand["estimated_min_units"] == 24
    assert estimated.award_demand["epistemic"] == "INFERENCE"


def test_timing_comercial_nao_considera_evento_amanha_como_oportunidade_perfeita():
    from services.prospecting.event_intelligence import score_event_timing

    tomorrow = date.today() + timedelta(days=1)
    ideal = date.today() + timedelta(days=45)
    too_early = date.today() + timedelta(days=260)
    late_score = score_event_timing(tomorrow)
    ideal_score = score_event_timing(ideal)
    early_score = score_event_timing(too_early)

    assert late_score["purchase_window"] == "late"
    assert late_score["timing_score"] < ideal_score["timing_score"]
    assert ideal_score["purchase_window"] == "ideal"
    assert ideal_score["timing_score"] >= 88
    assert early_score["purchase_window"] == "early"


def test_benchmark_sintetico_e_gate_de_release():
    from services.prospecting.quality_benchmark import assert_release_quality, run_quality_benchmark

    report = run_quality_benchmark()
    assert report["benchmark_kind"] == "synthetic_regression"
    assert report["real_conversion_claim"] is False
    assert report["routing_accuracy"] == 1.0
    assert report["high_confidence_false_positive_rate"] == 0.0
    assert report["evidence_coverage"] == 1.0
    assert_release_quality(report)


def test_motor_continua_generico_para_oferta_nao_prevista_no_core():
    from services.prospecting.offer_matcher import OfferMatcher
    from services.prospecting.offer_profile import OfferProfile, OfferProfileRegistry

    registry = OfferProfileRegistry()
    registry.register(OfferProfile(
        key="servico_novo",
        archetype="generic_b2b",
        vertical="custom",
        version="1.0",
        signals={
            "positive": ["HAS_CNPJ", "HAS_BUSINESS_EMAIL"],
            "weights": {"HAS_CNPJ": 1.0, "HAS_BUSINESS_EMAIL": 2.0},
        },
        qualification={
            "quality_gates": {
                "strong_evidence_any": ["HAS_BUSINESS_EMAIL"],
                "max_score_without_strong_evidence": 55,
            },
        },
    ))
    result = OfferMatcher(registry).match({
        "company_name": "Empresa nova",
        "has_cnpj": True,
        "has_business_email": True,
    })
    assert result[0].offer_key == "servico_novo"
    assert result[0].score_breakdown["strong_evidence_matched"] == ["HAS_BUSINESS_EMAIL"]
