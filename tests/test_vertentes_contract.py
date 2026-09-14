"""Contrato canônico de Vertentes baseado em OfferProfile."""
from __future__ import annotations

import inspect


FACTORY_KEYS = {
    "landing_page",
    "web_systems_erp",
    "mechanical_project",
    "technical_drawing",
    "machine_manual",
    "trophies",
    "trophies_sports",
    "trophies_mej",
    "3d_printing",
    "laser_cutting_technical",
    "laser_custom_products",
}


def _registry():
    from services.prospecting.effective_offer_registry import build_effective_registry
    return build_effective_registry(None, None)


def test_vertentes_read_api_aceita_membro_operacional_sem_gate_de_analyst():
    """Consultor usa /api/vertentes para criar campanha; leitura não pode exigir ANALYST."""
    from src.auth.dependencies import get_user_membership
    from src.routes.vertentes import get_vertente, list_vertentes

    for endpoint in (list_vertentes, get_vertente):
        dependency = inspect.signature(endpoint).parameters["_member"].default.dependency
        assert dependency is get_user_membership


def test_todas_vertentes_factory_cumprem_contrato_de_maturidade():
    from services.prospecting.offer_profile_maturity import evaluate_offer_profile_maturity

    registry = _registry()
    assert FACTORY_KEYS.issubset({profile.key for profile in registry.list()})
    for profile in registry.list():
        report = evaluate_offer_profile_maturity(profile)
        assert report.score >= 85, (profile.key, report.to_dict())


def test_trofeus_mej_e_esporte_sao_vertentes_distintas_e_event_driven():
    registry = _registry()
    sports = registry.get("trophies_sports")
    mej = registry.get("trophies_mej")

    assert sports is not None and mej is not None
    assert sports.key != mej.key
    assert "event_search" in sports.discovery["providers"]
    assert "event_search" in mej.discovery["providers"]
    assert "EVENT_SCHEDULED" in sports.signals["positive"]
    assert "EVENT_SCHEDULED" in mej.signals["positive"]
    assert any("MEJ" in str(item).upper() or "EMPRESA JÚNIOR" in str(item).upper() for item in mej.icp["segments"])


def test_golden_path_projeto_mecanico_prefere_evidencia_industrial_forte():
    from services.prospecting.offer_matcher import OfferMatcher

    matches = {item.offer_key: item for item in OfferMatcher(_registry()).match({
        "company_name": "Fábrica em expansão",
        "segment": "metalúrgica",
        "company_size": "EPP",
        "cnae": "25.11",
        "has_production_line": True,
        "expanding_factory": True,
        "new_equipment": True,
    })}
    opportunity = matches["mechanical_project"]
    assert opportunity.score >= 60
    assert opportunity.score_breakdown["strong_evidence_matched"]


def test_golden_path_manual_maquina_exige_contexto_tecnico_real():
    from services.prospecting.offer_matcher import OfferMatcher

    matches = {item.offer_key: item for item in OfferMatcher(_registry()).match({
        "company_name": "Fabricante de equipamentos",
        "segment": "fabricantes de máquinas",
        "company_size": "EPP",
        "machine_manufacturer": True,
        "new_machine": True,
        "nr12": True,
        "technical_documentation": True,
    })}
    opportunity = matches["machine_manual"]
    assert opportunity.score >= 60
    assert "NR12" in opportunity.score_breakdown["strong_evidence_matched"]


def test_golden_path_desenho_tecnico_valoriza_engenharia_reversa_e_pecas():
    from services.prospecting.offer_matcher import OfferMatcher

    matches = {item.offer_key: item for item in OfferMatcher(_registry()).match({
        "company_name": "Usinagem sob encomenda",
        "segment": "usinagem",
        "company_size": "ME",
        "custom_parts": True,
        "reverse_engineering": True,
        "replacement_parts": True,
        "usinagem": True,
    })}
    opportunity = matches["technical_drawing"]
    assert opportunity.score >= 60
    assert "REVERSE_ENGINEERING" in opportunity.score_breakdown["strong_evidence_matched"]


def test_trofeus_sem_evento_nao_recebe_confianca_alta_so_por_instagram():
    from services.prospecting.offer_matcher import OfferMatcher

    matches = {item.offer_key: item for item in OfferMatcher(_registry()).match({
        "company_name": "Organização sem evento confirmado",
        "segment": "eventos",
        "company_size": "ME",
        "has_instagram": True,
    })}
    trophies = matches["trophies"]
    assert trophies.score <= 52
    assert "missing_strong_evidence" in trophies.score_breakdown["capped_by"]


def test_golden_path_mej_prioriza_evento_com_timing_e_organizador():
    from services.prospecting.offer_matcher import OfferMatcher

    matches = {item.offer_key: item for item in OfferMatcher(_registry()).match({
        "company_name": "Núcleo de Empresas Juniores",
        "segment": "MEJ",
        "company_size": "ME",
        "event_scheduled": True,
        "hosts_events": True,
        "seasonal_demand": True,
        "has_instagram": True,
    })}
    opportunity = matches["trophies_mej"]
    assert opportunity.score >= 60
    assert opportunity.score_breakdown["confidence_band"] in {"medium", "high"}
    assert "EVENT_SCHEDULED" in opportunity.score_breakdown["strong_evidence_matched"]
