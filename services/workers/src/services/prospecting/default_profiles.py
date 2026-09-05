"""Perfis iniciais de OfferProfile — Fase B do plano de consolidação.

Adicionar nova oferta = criar profile aqui. Engine não muda (consolidação §Fase B).
"""
from typing import Any, Dict

from services.prospecting.offer_profile import (
    OfferProfile,
    OfferProfileRegistry,
)


def build_default_registry() -> OfferProfileRegistry:
    """Constrói o registry com os profiles iniciais.

    Cada profile é uma unidade de inteligência comercial completa:
    ICP + discovery + prescoring + signals + intent + decision_makers +
    channels + qualification + outreach.
    """
    registry = OfferProfileRegistry()

    # ---- web_presence: landing page ----
    registry.register(OfferProfile(
        key="landing_page",
        archetype="web_presence",
        vertical="digital",
        version="1.0",
        offer={"name": "Landing Page de Conversão", "tagline": "Página de alta conversão"},
        icp={
            "company_sizes": ["ME", "PE"],  # micro/pequena
            "segments": ["psicologia", "estética", "clínicas", "infoprodutores"],
            "cnaes": ["8630-5/04", "9602-5/02", "8599-6/99"],
            "exclusions": ["enterprise com site"],
            "geography": {"country": "BR", "states": ["SP", "RJ", "MG"]},
        },
        discovery={
            "providers": ["google_places", "instagram_search"],
            "target_candidates": 300,
            "provider_budgets": {"google_places": 100, "instagram_search": 50},
            "query_strategy": "service+segment+city",
        },
        prescoring={
            "required_signals": ["HAS_PHONE", "GOOGLE_RATING"],
            "weights": {
                "NO_OWN_WEBSITE": 25, "HAS_INSTAGRAM": 12,
                "HAS_PHONE": 8, "GOOGLE_RATING": 15, "GOOGLE_RATING_COUNT": 15,
            },
            "threshold": 50, "top_k": 30, "on_insufficient_data": "discard",
        },
        enrichment={
            "steps": ["cnpj_receita", "technical_site"],
            "stop_conditions": {"if_qualifies_after": "technical_site"},
            "max_cost": 5,
        },
        signals={
            "positive": ["NO_OWN_WEBSITE", "HAS_INSTAGRAM"],
            "negative": ["HAS_OWN_WEBSITE_INSTITUTIONAL"],
            "disqualifiers": ["ENTERPRISE"],
        },
        intent={
            "event_weights": {"HIRING": 0.7, "EXPANDING": 0.5},
            "decay_days": 90, "trigger_threshold": 0.6,
        },
        decision_makers={
            "roles": ["marketing_manager", "founder", "product_manager"],
            "buyer_types": ["ECONOMIC_BUYER", "CHAMPION"],
            "priority": ["founder", "marketing_manager", "product_manager"],
        },
        channels={"priority": ["email", "instagram", "phone"]},
        qualification={
            "questions": [
                "Qual o objetivo principal do site?",
                "Quando foi a última atualização?",
                "Depende de agência ou interno?",
            ],
        },
        outreach={
            "angle": "presença_digital",
            "evidence_requirements": ["NO_OWN_WEBSITE", "GOOGLE_RATING"],
        },
    ))

    # ---- industrial: mechanical_project ----
    registry.register(OfferProfile(
        key="mechanical_project",
        archetype="industrial",
        vertical="mechanical_engineering",
        version="1.0",
        offer={"name": "Projeto Mecânico", "tagline": "Projeto mecânico sob medida"},
        icp={
            "company_sizes": ["EPP", "ME", "GE"],  # pequena/média/grande
            "segments": ["metalúrgica", "máquinas industriais", "automação"],
            "cnaes": ["25", "28", "33"],  # indústria
            "exclusions": ["varejo", "serviços não-industriais"],
        },
        discovery={
            "providers": ["cnae_discovery", "google_places"],
            "target_candidates": 200,
            "provider_budgets": {"cnae_discovery": 100, "google_places": 50},
            "query_strategy": "cnae+city",
        },
        prescoring={
            "required_signals": ["HAS_PHONE", "HAS_CNPJ"],
            "weights": {
                "HAS_PHONE": 15, "HAS_CNPJ": 20,
                "GOOGLE_RATING": 5, "GOOGLE_RATING_COUNT": 5,
            },
            "threshold": 40, "top_k": 25, "on_insufficient_data": "promote",
        },
        enrichment={
            "steps": ["cnpj_receita", "business_social", "cnpj_qsa"],
            "stop_conditions": {},
            "max_cost": 3,
        },
        signals={
            "positive": ["HAS_CNPJ", "HAS_BUSINESS_EMAIL"],
            "negative": ["RETAIL_FOCUSED"],
            "disqualifiers": ["SERVICE_ONLY"],
        },
        intent={
            "event_weights": {"HIRING": 0.8, "NEW_EQUIPMENT": 0.9, "EXPANDING": 0.7},
            "decay_days": 60, "trigger_threshold": 0.5,
        },
        decision_makers={
            "roles": ["plant_engineer", "maintenance_manager", "operations_director"],
            "buyer_types": ["TECHNICAL_BUYER", "ECONOMIC_BUYER"],
            "priority": ["operations_director", "plant_engineer", "maintenance_manager"],
        },
        channels={"priority": ["email", "phone", "linkedin"]},
        qualification={
            "questions": [
                "Qual a capacidade instalada atual?",
                "Terceiriza parte da produção?",
                "Previsão de expansão 12 meses?",
            ],
        },
        outreach={
            "angle": "capacidade_industrial",
            "evidence_requirements": ["HAS_CNPJ", "CNAE_INDUSTRIAL"],
        },
    ))

    # ---- industrial: technical_drawing ----
    registry.register(OfferProfile(
        key="technical_drawing",
        archetype="industrial",
        vertical="mechanical_engineering",
        version="1.0",
        offer={"name": "Desenho Técnico", "tagline": "Desenho técnico e detalhamento"},
        icp={
            "company_sizes": ["EPP", "ME"],
            "segments": ["projetos sob demanda", "indústria sob encomenda"],
            "cnaes": ["25", "71"],  # indústria + engenharia
        },
        discovery={
            "providers": ["cnae_discovery", "google_places"],
            "target_candidates": 150,
            "query_strategy": "cnae+city",
        },
        prescoring={
            "weights": {"HAS_PHONE": 15, "HAS_CNPJ": 20},
            "threshold": 35, "top_k": 20,
        },
        decision_makers={
            "roles": ["designer", "engineering_manager", "procurement"],
            "buyer_types": ["TECHNICAL_BUYER"],
        },
        channels={"priority": ["email", "phone"]},
    ))

    # ---- industrial: machine_manual ----
    registry.register(OfferProfile(
        key="machine_manual",
        archetype="industrial",
        vertical="mechanical_engineering",
        version="1.0",
        offer={"name": "Manual de Máquinas", "tagline": "Documentação técnica NR-12"},
        icp={
            "company_sizes": ["EPP", "ME", "GE"],
            "segments": ["fabricantes de máquinas", "indústria com frota de equipamentos"],
            "cnaes": ["28"],  # máquinas
        },
        discovery={
            "providers": ["cnae_discovery"],
            "target_candidates": 100,
        },
        decision_makers={
            "roles": ["plant_engineer", "safety_manager", "operations_director"],
            "buyer_types": ["TECHNICAL_BUYER", "ECONOMIC_BUYER"],
        },
        qualification={
            "questions": [
                "Quantas máquinas precisam de manual?",
                "Já possuem documentação técnica?",
                "Conformidade com NR-12?",
            ],
        },
    ))

    # ---- custom_products: trophies ----
    registry.register(OfferProfile(
        key="trophies",
        archetype="custom_products",
        vertical="awards",
        version="1.0",
        offer={"name": "Troféus Personalizados", "tagline": "Troféus para eventos esportivos e corporativos"},
        icp={
            "company_sizes": ["ME", "PE"],
            "segments": ["esportivos", "corporativos", "eventos", "federações"],
            "cnaes": ["32"],  # fabricação de produtos diversos
            "geography": {"country": "BR", "states": ["SP", "RJ", "MG", "RS"]},
        },
        discovery={
            "providers": ["google_places", "instagram_search", "event_search"],
            "target_candidates": 400,
            "provider_budgets": {
                "google_places": 100, "instagram_search": 50, "event_search": 80,
            },
            "query_strategy": "evento+cidade OR empresa+segmento",
        },
        prescoring={
            "weights": {
                "HAS_PHONE": 12, "HAS_INSTAGRAM": 15, "GOOGLE_RATING": 10,
                "GOOGLE_RATING_COUNT": 10, "HOSTS_EVENTS": 20,
            },
            "threshold": 45, "top_k": 40,
        },
        signals={
            "positive": ["HOSTS_EVENTS", "HAS_INSTAGRAM"],
            "disqualifiers": ["ONLINE_ONLY_RESALE"],
        },
        intent={
            "event_weights": {"EVENT_SCHEDULED": 0.9, "SEASONAL_DEMAND": 0.7},
            "decay_days": 30,  # eventos têm ciclo curto
            "trigger_threshold": 0.4,
        },
        decision_makers={
            "roles": ["event_manager", "marketing_director", "founder"],
            "buyer_types": ["ECONOMIC_BUYER", "CHAMPION"],
        },
        channels={"priority": ["whatsapp", "instagram", "email", "phone"]},
        qualification={
            "questions": [
                "Que tipo de evento/competição vocês organizam?",
                "Volume estimado de troféus?",
                "Já trabalham com fornecedor?",
            ],
        },
        outreach={
            "angle": "temporada_eventos",
            "evidence_requirements": ["HOSTS_EVENTS"],
        },
    ))

    return registry


def get_default_registry() -> OfferProfileRegistry:
    """Singleton lazy — registry padrão carregado uma vez."""
    global _default_registry
    if _default_registry is None:
        _default_registry = build_default_registry()
    return _default_registry


_default_registry = None
