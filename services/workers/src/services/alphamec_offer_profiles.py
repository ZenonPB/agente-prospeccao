"""Configuração declarativa das ofertas comerciais da AlphaMec.

Nomes e sinais específicos do portfólio ficam fora do núcleo genérico de
prospecção para que o motor continue reutilizável por outras organizações.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from services.prospecting.offer_profile import OfferProfile, OfferProfileRegistry


def _deep_merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    result = dict(base or {})
    for key, value in extra.items():
        current = result.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            result[key] = _deep_merge(current, value)
        elif isinstance(current, list) and isinstance(value, list):
            result[key] = list(dict.fromkeys([*current, *value]))
        else:
            result[key] = value
    return result


def _enhance(registry: OfferProfileRegistry, key: str, **sections: dict[str, Any]) -> None:
    current = registry.get(key)
    if current is None:
        return
    registry.register(replace(
        current,
        version="1.1",
        signals=_deep_merge(current.signals, sections.get("signals") or {}),
        intent=_deep_merge(current.intent, sections.get("intent") or {}),
        decision_makers=_deep_merge(current.decision_makers, sections.get("decision_makers") or {}),
        outreach=_deep_merge(current.outreach, sections.get("outreach") or {}),
    ))


def _register_if_missing(registry: OfferProfileRegistry, profile: OfferProfile) -> None:
    if registry.get(profile.key) is None:
        registry.register(profile)


def register_alphamec_profiles(registry: OfferProfileRegistry) -> OfferProfileRegistry:
    """Registra e aprimora perfis do portfólio sem alterar o núcleo genérico."""
    _enhance(
        registry,
        "landing_page",
        signals={
            "optional_positive": ["HAS_ADS", "WEAK_CTA", "NO_CONTACT_FORM", "WEAK_CONVERSION_FLOW"],
            "weights": {"HAS_ADS": 1.2, "WEAK_CTA": 1.1, "NO_CONTACT_FORM": 1.15, "WEAK_CONVERSION_FLOW": 1.15},
        },
        decision_makers={
            "roles": ["founder", "marketing_manager", "commercial_manager"],
            "priority": ["founder", "marketing_manager", "commercial_manager"],
        },
    )
    _enhance(
        registry,
        "mechanical_project",
        signals={
            "optional_positive": ["HAS_PRODUCTION_LINE", "CUSTOM_MACHINERY", "AUTOMATION", "EXPANDING_FACTORY", "HIRING_MECHANICAL_ENGINEER"],
            "weights": {"HAS_PRODUCTION_LINE": 1.15, "CUSTOM_MACHINERY": 1.3, "EXPANDING_FACTORY": 1.2, "HIRING_MECHANICAL_ENGINEER": 1.1},
        },
        intent={"event_weights": {"EXPANDING_FACTORY": 0.9, "HIRING_MECHANICAL_ENGINEER": 0.85}},
    )
    _enhance(
        registry,
        "technical_drawing",
        signals={
            "optional_positive": ["USINAGEM", "CUSTOM_PARTS", "REPLACEMENT_PARTS", "REVERSE_ENGINEERING", "CUSTOM_MANUFACTURING"],
            "weights": {"CUSTOM_PARTS": 1.25, "REVERSE_ENGINEERING": 1.25, "CUSTOM_MANUFACTURING": 1.15},
        },
    )
    _enhance(
        registry,
        "machine_manual",
        signals={
            "optional_positive": ["MACHINE_MANUFACTURER", "NR12", "INDUSTRIAL_SAFETY", "TECHNICAL_DOCUMENTATION", "NEW_MACHINE"],
            "weights": {"NR12": 1.3, "TECHNICAL_DOCUMENTATION": 1.2, "NEW_MACHINE": 1.15},
        },
    )
    _enhance(
        registry,
        "trophies",
        signals={"optional_positive": ["EVENT_SCHEDULED", "SEASONAL_DEMAND"]},
        intent={"event_weights": {"EVENT_SCHEDULED": 0.95, "SEASONAL_DEMAND": 0.8}},
    )

    profiles = [
        OfferProfile(
            key="web_systems_erp",
            archetype="digital_systems",
            vertical="technology",
            offer={"name": "Sistemas Web / ERP", "tagline": "Software sob medida para operação real"},
            icp={"company_sizes": ["ME", "EPP", "GE"], "segments": ["serviços", "indústria", "distribuição", "operações multiunidade"]},
            discovery={"providers": ["google_places", "cnae_discovery", "job_search"], "target_candidates": 250, "query_strategy": "segment+operations+city"},
            prescoring={"weights": {"MULTI_UNIT": 18, "MANUAL_PROCESS": 20, "HIRING_OPERATIONS": 18, "HIRING_IT": 18, "EXPANDING": 14}, "threshold": 38, "top_k": 35, "on_insufficient_data": "promote"},
            enrichment={"steps": ["cnpj_receita", "technical_site", "business_social"], "max_cost": 5, "people_discovery": {"max_cost": 3, "max_steps": 2, "min_role_fit": 70}},
            signals={"positive": ["MULTI_UNIT", "MANUAL_PROCESS", "HIRING_OPERATIONS", "HIRING_IT", "EXPANDING", "USES_SPREADSHEETS", "SAAS_LIMITATION"], "negative": ["VERY_SMALL_LOW_COMPLEXITY"], "weights": {"MANUAL_PROCESS": 1.3, "MULTI_UNIT": 1.2, "HIRING_OPERATIONS": 1.1, "HIRING_IT": 1.1, "EXPANDING": 1.0}},
            intent={"event_weights": {"HIRING_OPERATIONS": 0.9, "HIRING_IT": 0.85, "EXPANDING": 0.8, "NEW_BRANCH": 0.8}, "decay_days": 75, "trigger_threshold": 0.5},
            decision_makers={"roles": ["founder", "operations_director", "finance_manager", "it_manager"], "buyer_types": ["ECONOMIC_BUYER", "TECHNICAL_BUYER", "CHAMPION"], "priority": ["operations_director", "founder", "it_manager", "finance_manager"]},
            channels={"priority": ["email", "phone", "linkedin"]},
            qualification={"questions": ["Qual processo hoje exige mais trabalho manual?", "Quais ferramentas precisam trocar dados entre si?", "Há retrabalho, planilhas paralelas ou limitações do sistema atual?"]},
            outreach={"angle": "eficiencia_operacional", "evidence_requirements": ["MANUAL_PROCESS"]},
        ),
        OfferProfile(
            key="3d_printing",
            archetype="rapid_prototyping",
            vertical="additive_manufacturing",
            offer={"name": "Impressão 3D", "tagline": "Protótipos e peças com ciclo rápido"},
            icp={"company_sizes": ["ME", "EPP", "GE"], "segments": ["P&D", "hardware", "produto", "laboratórios", "manufatura"]},
            discovery={"providers": ["cnae_discovery", "google_places", "job_search", "company_news"], "target_candidates": 180, "query_strategy": "rnd+product+manufacturing"},
            prescoring={"weights": {"NEW_PRODUCT": 22, "PROTOTYPE": 25, "R_AND_D": 22, "HAS_CNPJ": 10}, "threshold": 35, "top_k": 30, "on_insufficient_data": "promote"},
            enrichment={"steps": ["cnpj_receita", "business_social"], "max_cost": 4, "people_discovery": {"max_cost": 2, "max_steps": 2, "min_role_fit": 70}},
            signals={"positive": ["NEW_PRODUCT", "PROTOTYPE", "R_AND_D", "CUSTOM_PARTS"], "weights": {"PROTOTYPE": 1.35, "R_AND_D": 1.25, "NEW_PRODUCT": 1.15}},
            intent={"event_weights": {"NEW_PRODUCT": 0.95, "PROTOTYPE": 1.0, "R_AND_D": 0.9}, "decay_days": 45, "trigger_threshold": 0.45},
            decision_makers={"roles": ["engineering_manager", "product_manager", "founder", "rnd_manager"], "buyer_types": ["TECHNICAL_BUYER", "ECONOMIC_BUYER", "CHAMPION"]},
            channels={"priority": ["email", "linkedin", "phone"]},
            outreach={"angle": "validacao_rapida", "evidence_requirements": ["NEW_PRODUCT"]},
        ),
        OfferProfile(
            key="laser_cutting_technical",
            archetype="industrial_fabrication",
            vertical="laser_fabrication",
            offer={"name": "Corte a Laser Técnico", "tagline": "Corte de peças e chapas sob especificação"},
            icp={"company_sizes": ["ME", "EPP", "GE"], "segments": ["metalúrgica", "manufatura", "máquinas", "produto"]},
            discovery={"providers": ["cnae_discovery", "google_places"], "target_candidates": 180, "query_strategy": "industrial+fabrication"},
            prescoring={"weights": {"CUSTOM_PARTS": 22, "USINAGEM": 16, "HAS_CNPJ": 12}, "threshold": 32, "top_k": 30},
            enrichment={"steps": ["cnpj_receita", "business_social"], "max_cost": 3, "people_discovery": {"max_cost": 2, "max_steps": 2, "min_role_fit": 70}},
            signals={"positive": ["CUSTOM_PARTS", "USINAGEM", "CUSTOM_MANUFACTURING", "NEW_EQUIPMENT"], "weights": {"CUSTOM_PARTS": 1.3, "CUSTOM_MANUFACTURING": 1.15}},
            intent={"event_weights": {"NEW_EQUIPMENT": 0.8, "NEW_PRODUCT": 0.8}, "decay_days": 60, "trigger_threshold": 0.45},
            decision_makers={"roles": ["engineering_manager", "procurement", "operations_director"], "buyer_types": ["TECHNICAL_BUYER", "ECONOMIC_BUYER"]},
            channels={"priority": ["email", "phone"]},
            outreach={"angle": "capacidade_fabricacao", "evidence_requirements": ["CUSTOM_PARTS"]},
        ),
        OfferProfile(
            key="laser_custom_products",
            archetype="custom_products",
            vertical="custom_laser_products",
            offer={"name": "Produtos Personalizados a Laser", "tagline": "Peças personalizadas em lotes flexíveis"},
            icp={"company_sizes": ["ME", "EPP"], "segments": ["eventos", "brindes", "comunicação", "varejo especializado", "instituições"]},
            discovery={"providers": ["google_places", "event_search", "instagram_search"], "target_candidates": 220, "query_strategy": "events+custom+city"},
            prescoring={"weights": {"EVENT_SCHEDULED": 20, "HAS_INSTAGRAM": 12, "SEASONAL_DEMAND": 16}, "threshold": 34, "top_k": 35},
            enrichment={"steps": ["business_social"], "max_cost": 3, "people_discovery": {"max_cost": 2, "max_steps": 2, "min_role_fit": 70}},
            signals={"positive": ["EVENT_SCHEDULED", "SEASONAL_DEMAND", "HAS_INSTAGRAM", "CUSTOM_PRODUCTS"]},
            intent={"event_weights": {"EVENT_SCHEDULED": 0.9, "SEASONAL_DEMAND": 0.75}, "decay_days": 35, "trigger_threshold": 0.4},
            decision_makers={"roles": ["event_manager", "marketing_director", "founder", "procurement"], "buyer_types": ["ECONOMIC_BUYER", "CHAMPION"]},
            channels={"priority": ["whatsapp", "instagram", "email"]},
            outreach={"angle": "personalizacao_evento", "evidence_requirements": ["EVENT_SCHEDULED"]},
        ),
    ]
    for profile in profiles:
        _register_if_missing(registry, profile)
    return registry


register_phase5_profiles = register_alphamec_profiles
