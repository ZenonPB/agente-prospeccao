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


def _enhance(registry: OfferProfileRegistry, key: str, *, version: str = "2.0", **sections: dict[str, Any]) -> None:
    current = registry.get(key)
    if current is None:
        return
    registry.register(replace(
        current,
        version=version,
        signals=_deep_merge(current.signals, sections.get("signals") or {}),
        intent=_deep_merge(current.intent, sections.get("intent") or {}),
        decision_makers=_deep_merge(current.decision_makers, sections.get("decision_makers") or {}),
        qualification=_deep_merge(current.qualification, sections.get("qualification") or {}),
        outreach=_deep_merge(current.outreach, sections.get("outreach") or {}),
        discovery=_deep_merge(current.discovery, sections.get("discovery") or {}),
        enrichment=_deep_merge(current.enrichment, sections.get("enrichment") or {}),
        prescoring=_deep_merge(current.prescoring, sections.get("prescoring") or {}),
        icp=_deep_merge(current.icp, sections.get("icp") or {}),
    ))


def _register_if_missing(registry: OfferProfileRegistry, profile: OfferProfile) -> None:
    if registry.get(profile.key) is None:
        registry.register(profile)


def register_alphamec_profiles(registry: OfferProfileRegistry) -> OfferProfileRegistry:
    """Registra e aprimora perfis do portfólio sem alterar o núcleo genérico.

    Golden Path aqui significa: quais evidências tornam uma oportunidade
    comercialmente forte, quais sinais são apenas apoio e quais condições
    impedem que um lead receba confiança alta cedo demais.
    """
    _enhance(
        registry,
        "landing_page",
        icp={
            "segments": [
                "psicologia", "estética", "clínicas", "infoprodutores",
                "odontologia", "advocacia", "academias", "serviços locais",
            ],
        },
        signals={
            "optional_positive": [
                "HAS_ADS", "WEAK_CTA", "NO_CONTACT_FORM", "WEAK_CONVERSION_FLOW",
            ],
            "weights": {
                "NO_OWN_WEBSITE": 1.8,
                "HAS_INSTAGRAM": 1.0,
                "HAS_ADS": 1.4,
                "WEAK_CTA": 1.25,
                "NO_CONTACT_FORM": 1.3,
                "WEAK_CONVERSION_FLOW": 1.35,
            },
            "negative_penalty_each": 18,
        },
        intent={
            "event_weights": {"HIRING": 0.55, "EXPANDING": 0.65, "HAS_ADS": 0.8},
            "decay_days": 75,
            "trigger_threshold": 0.45,
        },
        decision_makers={
            "roles": ["founder", "marketing_manager", "commercial_manager"],
            "priority": ["founder", "marketing_manager", "commercial_manager"],
        },
        qualification={
            "questions": [
                "Hoje, de onde vêm os novos clientes?",
                "Existe uma página dedicada para transformar interesse em contato?",
                "Vocês investem em anúncios ou conteúdo e conseguem medir quantos contatos viram clientes?",
            ],
            "quality_gates": {
                "strong_evidence_any": [
                    "NO_OWN_WEBSITE", "WEAK_CTA", "NO_CONTACT_FORM", "WEAK_CONVERSION_FLOW", "HAS_ADS",
                ],
                "min_observed_signals": 2,
                "max_score_without_strong_evidence": 58,
                "max_score_with_sparse_evidence": 52,
                "high_confidence_score": 80,
            },
        },
        outreach={
            "angle": "demanda_digital_sem_conversao",
            "evidence_requirements": [
                "NO_OWN_WEBSITE", "WEAK_CTA", "NO_CONTACT_FORM", "WEAK_CONVERSION_FLOW", "HAS_ADS",
            ],
        },
    )

    _enhance(
        registry,
        "mechanical_project",
        signals={
            "optional_positive": [
                "HAS_PRODUCTION_LINE", "CUSTOM_MACHINERY", "AUTOMATION",
                "EXPANDING_FACTORY", "HIRING_MECHANICAL_ENGINEER", "NEW_EQUIPMENT",
            ],
            "weights": {
                "HAS_CNPJ": 0.6,
                "HAS_BUSINESS_EMAIL": 0.5,
                "HAS_PHONE": 0.3,
                "HAS_PRODUCTION_LINE": 1.2,
                "CUSTOM_MACHINERY": 1.5,
                "AUTOMATION": 1.25,
                "EXPANDING_FACTORY": 1.45,
                "HIRING_MECHANICAL_ENGINEER": 1.1,
                "NEW_EQUIPMENT": 1.2,
            },
            "negative_penalty_each": 22,
        },
        intent={
            "event_weights": {
                "EXPANDING_FACTORY": 0.95,
                "HIRING_MECHANICAL_ENGINEER": 0.85,
                "NEW_EQUIPMENT": 0.9,
                "EXPANDING": 0.75,
            },
            "decay_days": 75,
            "trigger_threshold": 0.45,
        },
        qualification={
            "questions": [
                "Qual gargalo de produção, movimentação ou equipamento mais limita a operação hoje?",
                "Há expansão, novo equipamento ou adaptação planejada para os próximos meses?",
                "Esse problema exige solução sob medida ou já existe equipamento comercial adequado?",
            ],
            "quality_gates": {
                "strong_evidence_any": [
                    "HAS_PRODUCTION_LINE", "CUSTOM_MACHINERY", "AUTOMATION",
                    "EXPANDING_FACTORY", "HIRING_MECHANICAL_ENGINEER", "NEW_EQUIPMENT",
                ],
                "min_observed_signals": 2,
                "max_score_without_strong_evidence": 55,
                "max_score_with_sparse_evidence": 50,
                "high_confidence_score": 80,
            },
        },
        outreach={
            "angle": "gargalo_ou_expansao_industrial",
            "evidence_requirements": [
                "HAS_PRODUCTION_LINE", "CUSTOM_MACHINERY", "EXPANDING_FACTORY", "NEW_EQUIPMENT",
            ],
        },
    )

    _enhance(
        registry,
        "technical_drawing",
        signals={
            "optional_positive": [
                "USINAGEM", "CUSTOM_PARTS", "REPLACEMENT_PARTS",
                "REVERSE_ENGINEERING", "CUSTOM_MANUFACTURING",
            ],
            "weights": {
                "CUSTOM_PARTS": 1.4,
                "REVERSE_ENGINEERING": 1.45,
                "CUSTOM_MANUFACTURING": 1.2,
                "USINAGEM": 1.0,
            },
            "negative_penalty_each": 18,
        },
        qualification={
            "quality_gates": {
                "strong_evidence_any": [
                    "CUSTOM_PARTS", "REVERSE_ENGINEERING", "CUSTOM_MANUFACTURING", "USINAGEM",
                ],
                "max_score_without_strong_evidence": 58,
                "high_confidence_score": 78,
            },
        },
    )

    _enhance(
        registry,
        "machine_manual",
        signals={
            "optional_positive": [
                "MACHINE_MANUFACTURER", "NR12", "INDUSTRIAL_SAFETY",
                "TECHNICAL_DOCUMENTATION", "NEW_MACHINE",
            ],
            "weights": {
                "NR12": 1.5,
                "TECHNICAL_DOCUMENTATION": 1.35,
                "NEW_MACHINE": 1.25,
                "MACHINE_MANUFACTURER": 1.15,
            },
        },
        qualification={
            "quality_gates": {
                "strong_evidence_any": ["NR12", "TECHNICAL_DOCUMENTATION", "NEW_MACHINE", "MACHINE_MANUFACTURER"],
                "max_score_without_strong_evidence": 58,
                "high_confidence_score": 78,
            },
        },
    )

    _enhance(
        registry,
        "trophies",
        signals={
            "optional_positive": ["EVENT_SCHEDULED", "SEASONAL_DEMAND", "CUSTOM_PRODUCTS"],
            "weights": {
                "HOSTS_EVENTS": 1.5,
                "EVENT_SCHEDULED": 1.7,
                "SEASONAL_DEMAND": 1.25,
                "CUSTOM_PRODUCTS": 1.1,
            },
            "negative_penalty_each": 25,
        },
        intent={
            "event_weights": {"EVENT_SCHEDULED": 1.0, "SEASONAL_DEMAND": 0.85},
            "decay_days": 45,
            "trigger_threshold": 0.35,
        },
        qualification={
            "questions": [
                "Qual é a data do evento ou premiação?",
                "Quantas categorias, equipes ou reconhecimentos serão premiados?",
                "Quem aprova fornecedor, orçamento e personalização?",
            ],
            "quality_gates": {
                "strong_evidence_any": ["EVENT_SCHEDULED", "HOSTS_EVENTS", "SEASONAL_DEMAND"],
                "max_score_without_strong_evidence": 55,
                "high_confidence_score": 78,
            },
        },
        outreach={
            "angle": "evento_com_janela_de_compra",
            "evidence_requirements": ["EVENT_SCHEDULED", "HOSTS_EVENTS"],
        },
    )

    profiles = [
        OfferProfile(
            key="web_systems_erp",
            archetype="digital_systems",
            vertical="technology",
            version="2.0",
            offer={"name": "Sistemas Web sob Medida", "tagline": "Software para eliminar gargalos reais da operação"},
            icp={
                "company_sizes": ["ME", "EPP", "GE"],
                "segments": ["serviços", "indústria", "distribuição", "logística", "operações multiunidade"],
                "exclusions": ["software house", "SaaS puro", "microoperação sem processo repetitivo"],
                "geography": {"country": "BR"},
            },
            discovery={
                "providers": ["google_places", "cnae_discovery", "job_search"],
                "target_candidates": 300,
                "provider_budgets": {"google_places": 100, "cnae_discovery": 120, "job_search": 80},
                "query_strategy": "segment+operations+growth+city",
            },
            prescoring={
                "weights": {
                    "MULTI_UNIT": 20, "MANUAL_PROCESS": 24, "USES_SPREADSHEETS": 22,
                    "SAAS_LIMITATION": 24, "HIRING_OPERATIONS": 16, "HIRING_IT": 14,
                    "EXPANDING": 14, "NEW_BRANCH": 14,
                },
                "threshold": 40,
                "top_k": 35,
                "on_insufficient_data": "review",
            },
            enrichment={
                "steps": ["cnpj_receita", "technical_site", "business_social"],
                "max_cost": 6,
                "people_discovery": {"max_cost": 3, "max_steps": 3, "min_role_fit": 72},
            },
            signals={
                "positive": [
                    "MULTI_UNIT", "MANUAL_PROCESS", "USES_SPREADSHEETS", "SAAS_LIMITATION",
                    "HIRING_OPERATIONS", "HIRING_IT", "EXPANDING", "NEW_BRANCH",
                ],
                "negative": ["VERY_SMALL_LOW_COMPLEXITY"],
                "negative_penalty_each": 30,
                "weights": {
                    "MANUAL_PROCESS": 1.5, "USES_SPREADSHEETS": 1.45,
                    "SAAS_LIMITATION": 1.5, "MULTI_UNIT": 1.3,
                    "HIRING_OPERATIONS": 1.05, "HIRING_IT": 1.0,
                    "EXPANDING": 1.0, "NEW_BRANCH": 1.1,
                },
            },
            intent={
                "event_weights": {
                    "HIRING_OPERATIONS": 0.85, "HIRING_IT": 0.75,
                    "EXPANDING": 0.8, "NEW_BRANCH": 0.85,
                },
                "decay_days": 120,
                "trigger_threshold": 0.45,
            },
            decision_makers={
                "roles": ["founder", "operations_director", "it_manager", "finance_manager"],
                "buyer_types": ["ECONOMIC_BUYER", "TECHNICAL_BUYER", "CHAMPION"],
                "priority": ["operations_director", "founder", "it_manager", "finance_manager"],
            },
            channels={"priority": ["email", "linkedin", "phone"]},
            qualification={
                "questions": [
                    "Qual processo hoje exige mais trabalho manual ou retrabalho?",
                    "Quais planilhas/sistemas precisam trocar dados entre si?",
                    "Quantas pessoas ou unidades dependem desse processo?",
                    "O sistema atual limita a operação em quê?",
                ],
                "quality_gates": {
                    "strong_evidence_any": [
                        "MANUAL_PROCESS", "USES_SPREADSHEETS", "SAAS_LIMITATION", "MULTI_UNIT",
                    ],
                    "min_observed_signals": 2,
                    "max_score_without_strong_evidence": 56,
                    "max_score_with_sparse_evidence": 50,
                    "high_confidence_score": 80,
                },
            },
            outreach={
                "angle": "gargalo_operacional_com_impacto",
                "evidence_requirements": ["MANUAL_PROCESS", "USES_SPREADSHEETS", "SAAS_LIMITATION", "MULTI_UNIT"],
            },
        ),
        OfferProfile(
            key="trophies_sports",
            archetype="custom_products",
            vertical="awards_sports",
            version="2.0",
            offer={"name": "Troféus para Eventos Esportivos", "tagline": "Premiações personalizadas para campeonatos e provas"},
            icp={
                "company_sizes": ["ME", "PE", "EPP"],
                "segments": ["campeonatos", "corridas", "ligas", "federações", "clubes", "associações esportivas"],
                "geography": {"country": "BR"},
            },
            discovery={
                "providers": ["event_search", "google_places", "instagram_search"],
                "target_candidates": 450,
                "provider_budgets": {"event_search": 180, "google_places": 120, "instagram_search": 80},
                "query_strategy": "competition+organizer+date+region",
            },
            prescoring={
                "weights": {"EVENT_SCHEDULED": 30, "HOSTS_EVENTS": 24, "SEASONAL_DEMAND": 18, "HAS_PHONE": 8},
                "threshold": 42,
                "top_k": 50,
                "on_insufficient_data": "review",
            },
            enrichment={
                "steps": ["business_social"],
                "max_cost": 4,
                "people_discovery": {"max_cost": 3, "max_steps": 3, "min_role_fit": 70},
            },
            signals={
                "positive": ["EVENT_SCHEDULED", "HOSTS_EVENTS", "SEASONAL_DEMAND", "CUSTOM_PRODUCTS"],
                "negative": ["ONLINE_ONLY_RESALE"],
                "negative_penalty_each": 30,
                "weights": {"EVENT_SCHEDULED": 1.7, "HOSTS_EVENTS": 1.5, "SEASONAL_DEMAND": 1.2, "CUSTOM_PRODUCTS": 1.0},
            },
            intent={"event_weights": {"EVENT_SCHEDULED": 1.0, "SEASONAL_DEMAND": 0.85}, "decay_days": 40, "trigger_threshold": 0.3},
            decision_makers={
                "roles": ["event_manager", "sports_director", "marketing_director", "founder", "procurement"],
                "buyer_types": ["ECONOMIC_BUYER", "CHAMPION", "TECHNICAL_BUYER"],
                "priority": ["event_manager", "sports_director", "procurement", "founder"],
            },
            channels={"priority": ["whatsapp", "email", "instagram", "phone"]},
            qualification={
                "questions": [
                    "Quando acontece a competição?",
                    "Quantas categorias e colocações serão premiadas?",
                    "Já existe fornecedor definido para troféus/medalhas?",
                ],
                "quality_gates": {
                    "strong_evidence_any": ["EVENT_SCHEDULED", "HOSTS_EVENTS"],
                    "max_score_without_strong_evidence": 52,
                    "high_confidence_score": 78,
                },
            },
            outreach={"angle": "premiacao_esportiva_com_timing", "evidence_requirements": ["EVENT_SCHEDULED", "HOSTS_EVENTS"]},
        ),
        OfferProfile(
            key="trophies_mej",
            archetype="custom_products",
            vertical="awards_mej",
            version="2.0",
            offer={"name": "Troféus para Eventos do MEJ", "tagline": "Premiações e reconhecimentos para EJs, núcleos e eventos do Movimento Empresa Júnior"},
            icp={
                "company_sizes": ["ME", "PE", "EPP"],
                "segments": [
                    "MEJ", "empresa júnior", "empresas juniores", "núcleo de empresas juniores",
                    "federação de empresas juniores", "evento universitário", "hackathon", "premiação universitária",
                ],
                "geography": {"country": "BR"},
            },
            discovery={
                "providers": ["event_search", "instagram_search", "google_places"],
                "target_candidates": 500,
                "provider_budgets": {"event_search": 220, "instagram_search": 120, "google_places": 80},
                "query_strategy": "mej+ej+nucleo+federacao+evento+edicao+data",
            },
            prescoring={
                "weights": {"EVENT_SCHEDULED": 32, "HOSTS_EVENTS": 24, "SEASONAL_DEMAND": 22, "HAS_INSTAGRAM": 10},
                "threshold": 40,
                "top_k": 60,
                "on_insufficient_data": "review",
            },
            enrichment={
                "steps": ["business_social"],
                "max_cost": 4,
                "people_discovery": {"max_cost": 3, "max_steps": 3, "min_role_fit": 68},
            },
            signals={
                "positive": ["EVENT_SCHEDULED", "HOSTS_EVENTS", "SEASONAL_DEMAND", "HAS_INSTAGRAM", "CUSTOM_PRODUCTS"],
                "negative": ["ONLINE_ONLY_RESALE"],
                "negative_penalty_each": 30,
                "weights": {
                    "EVENT_SCHEDULED": 1.75, "HOSTS_EVENTS": 1.45,
                    "SEASONAL_DEMAND": 1.4, "HAS_INSTAGRAM": 0.7, "CUSTOM_PRODUCTS": 1.0,
                },
            },
            intent={"event_weights": {"EVENT_SCHEDULED": 1.0, "SEASONAL_DEMAND": 0.9}, "decay_days": 55, "trigger_threshold": 0.3},
            decision_makers={
                "roles": ["event_manager", "president", "commercial_director", "marketing_director", "project_manager", "founder"],
                "buyer_types": ["ECONOMIC_BUYER", "CHAMPION"],
                "priority": ["event_manager", "president", "commercial_director", "project_manager"],
            },
            channels={"priority": ["whatsapp", "instagram", "email", "linkedin"]},
            qualification={
                "questions": [
                    "Qual é o evento/edição e quando acontece?",
                    "Haverá premiação, reconhecimento de EJs ou categorias competitivas?",
                    "Quem está responsável por fornecedores e orçamento nesta edição?",
                    "Há histórico de premiações em edições anteriores?",
                ],
                "quality_gates": {
                    "strong_evidence_any": ["EVENT_SCHEDULED", "HOSTS_EVENTS", "SEASONAL_DEMAND"],
                    "min_observed_signals": 2,
                    "max_score_without_strong_evidence": 50,
                    "max_score_with_sparse_evidence": 48,
                    "high_confidence_score": 78,
                },
            },
            outreach={"angle": "edicao_mej_com_janela_de_compra", "evidence_requirements": ["EVENT_SCHEDULED", "HOSTS_EVENTS"]},
        ),
        OfferProfile(
            key="3d_printing",
            archetype="rapid_prototyping",
            vertical="additive_manufacturing",
            version="2.0",
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
            version="2.0",
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
            version="2.0",
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
