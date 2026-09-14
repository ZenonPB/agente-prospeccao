"""Equalização comercial das Vertentes factory da AlphaMec.

O núcleo continua genérico. Este módulo completa somente inteligência específica
do portfólio AlphaMec e é aplicado sobre o registry efetivo, sem criar uma
segunda fonte de verdade para a estratégia comercial.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from services.prospecting.offer_profile import OfferProfileRegistry


def _merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    result = dict(base or {})
    for key, value in extra.items():
        current = result.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            result[key] = _merge(current, value)
        elif isinstance(current, list) and isinstance(value, list):
            result[key] = list(dict.fromkeys([*current, *value]))
        else:
            result[key] = value
    return result


def _enhance(registry: OfferProfileRegistry, key: str, *, version: str = "2.1", **sections: dict[str, Any]) -> None:
    profile = registry.get(key)
    if profile is None:
        return
    registry.register(replace(
        profile,
        version=version,
        offer=_merge(profile.offer, sections.get("offer") or {}),
        icp=_merge(profile.icp, sections.get("icp") or {}),
        discovery=_merge(profile.discovery, sections.get("discovery") or {}),
        prescoring=_merge(profile.prescoring, sections.get("prescoring") or {}),
        enrichment=_merge(profile.enrichment, sections.get("enrichment") or {}),
        signals=_merge(profile.signals, sections.get("signals") or {}),
        intent=_merge(profile.intent, sections.get("intent") or {}),
        decision_makers=_merge(profile.decision_makers, sections.get("decision_makers") or {}),
        channels=_merge(profile.channels, sections.get("channels") or {}),
        qualification=_merge(profile.qualification, sections.get("qualification") or {}),
        outreach=_merge(profile.outreach, sections.get("outreach") or {}),
    ))


def _set_signal_roles(
    registry: OfferProfileRegistry,
    key: str,
    *,
    positive: list[str],
    optional_positive: list[str],
    negative: list[str],
) -> None:
    """Separa fit comercial de sinais auxiliares sem misturar disponibilidade de contato."""
    profile = registry.get(key)
    if profile is None:
        return
    signals = dict(profile.signals or {})
    signals["positive"] = list(dict.fromkeys(positive))
    signals["optional_positive"] = list(dict.fromkeys(optional_positive))
    signals["negative"] = list(dict.fromkeys(negative))
    registry.register(replace(profile, signals=signals))


def equalize_alphamec_vertentes(registry: OfferProfileRegistry) -> OfferProfileRegistry:
    """Completa Golden Paths sem alterar profiles publicados pela organização.

    Deve ser aplicada ao catálogo-base antes dos overlays tenant-specific.
    """
    _enhance(
        registry,
        "mechanical_project",
        icp={
            "segments": ["metalúrgica", "máquinas industriais", "automação", "manufatura", "equipamentos industriais"],
            "exclusions": ["varejo", "serviços não-industriais", "software house"],
        },
        discovery={
            "providers": ["cnae_discovery", "google_places", "job_search", "company_news"],
            "target_candidates": 260,
            "provider_budgets": {"cnae_discovery": 110, "google_places": 70, "job_search": 50, "company_news": 30},
            "query_strategy": "industry+production+expansion+equipment+region",
        },
        prescoring={
            "weights": {
                "HAS_CNPJ": 12, "HAS_PHONE": 6, "CNAE_INDUSTRIAL": 18,
                "HAS_PRODUCTION_LINE": 24, "CUSTOM_MACHINERY": 26,
                "EXPANDING_FACTORY": 28, "NEW_EQUIPMENT": 22,
                "HIRING_MECHANICAL_ENGINEER": 18,
            },
            "threshold": 42,
            "top_k": 35,
            "on_insufficient_data": "review",
        },
        enrichment={
            "steps": ["cnpj_receita", "business_social"],
            "max_cost": 5,
            "people_discovery": {"max_cost": 3, "max_steps": 3, "min_role_fit": 72},
        },
        signals={
            "positive": ["HAS_PRODUCTION_LINE", "CUSTOM_MACHINERY", "AUTOMATION", "EXPANDING_FACTORY", "NEW_EQUIPMENT", "HIRING_MECHANICAL_ENGINEER"],
            "negative": ["RETAIL_FOCUSED", "SERVICE_ONLY"],
            "weights": {
                "HAS_PRODUCTION_LINE": 1.25, "CUSTOM_MACHINERY": 1.55,
                "AUTOMATION": 1.2, "EXPANDING_FACTORY": 1.55,
                "NEW_EQUIPMENT": 1.3, "HIRING_MECHANICAL_ENGINEER": 1.15,
            },
            "negative_penalty_each": 24,
        },
        intent={
            "event_weights": {"EXPANDING_FACTORY": 0.95, "NEW_EQUIPMENT": 0.9, "HIRING_MECHANICAL_ENGINEER": 0.82, "EXPANDING": 0.72},
            "decay_days": 90,
            "trigger_threshold": 0.4,
        },
        decision_makers={
            "roles": ["operations_director", "plant_engineer", "maintenance_manager", "engineering_manager", "procurement"],
            "priority": ["operations_director", "engineering_manager", "plant_engineer", "maintenance_manager", "procurement"],
        },
        channels={"priority": ["email", "linkedin", "phone"]},
        qualification={
            "questions": [
                "Qual gargalo físico ou produtivo precisa ser resolvido?",
                "Existe expansão, novo equipamento ou adaptação prevista?",
                "A solução precisa ser sob medida ou há equipamento comercial adequado?",
                "Qual impacto de produção, segurança ou capacidade esse problema gera?",
            ],
            "quality_gates": {
                "strong_evidence_any": ["HAS_PRODUCTION_LINE", "CUSTOM_MACHINERY", "EXPANDING_FACTORY", "NEW_EQUIPMENT", "HIRING_MECHANICAL_ENGINEER"],
                "min_observed_signals": 2,
                "max_score_without_strong_evidence": 55,
                "max_score_with_sparse_evidence": 50,
                "high_confidence_score": 80,
            },
        },
        outreach={
            "angle": "gargalo_ou_expansao_industrial",
            "evidence_requirements": ["HAS_PRODUCTION_LINE", "CUSTOM_MACHINERY", "EXPANDING_FACTORY", "NEW_EQUIPMENT"],
        },
    )

    _enhance(
        registry,
        "technical_drawing",
        icp={
            "segments": ["usinagem", "ferramentaria", "manutenção industrial", "fabricantes", "indústria sob encomenda"],
            "exclusions": ["varejo", "serviços sem fabricação ou manutenção técnica"],
        },
        discovery={
            "providers": ["cnae_discovery", "google_places", "job_search", "company_news"],
            "target_candidates": 220,
            "provider_budgets": {"cnae_discovery": 90, "google_places": 70, "job_search": 35, "company_news": 25},
            "query_strategy": "machining+custom-parts+reverse-engineering+region",
        },
        prescoring={
            "weights": {"HAS_CNPJ": 10, "CUSTOM_PARTS": 28, "REVERSE_ENGINEERING": 30, "CUSTOM_MANUFACTURING": 22, "USINAGEM": 18, "REPLACEMENT_PARTS": 22},
            "threshold": 38,
            "top_k": 30,
            "on_insufficient_data": "review",
        },
        enrichment={
            "steps": ["cnpj_receita", "business_social"],
            "max_cost": 4,
            "people_discovery": {"max_cost": 3, "max_steps": 3, "min_role_fit": 72},
        },
        signals={
            "positive": ["CUSTOM_PARTS", "REVERSE_ENGINEERING", "CUSTOM_MANUFACTURING", "USINAGEM", "REPLACEMENT_PARTS"],
            "negative": ["RETAIL_FOCUSED", "SERVICE_ONLY"],
            "weights": {"CUSTOM_PARTS": 1.45, "REVERSE_ENGINEERING": 1.55, "CUSTOM_MANUFACTURING": 1.25, "USINAGEM": 1.05, "REPLACEMENT_PARTS": 1.3},
            "negative_penalty_each": 20,
        },
        intent={
            "event_weights": {"NEW_EQUIPMENT": 0.75, "HIRING_MECHANICAL_ENGINEER": 0.65, "NEW_PRODUCT": 0.8},
            "decay_days": 90,
            "trigger_threshold": 0.45,
        },
        decision_makers={
            "roles": ["engineering_manager", "designer", "plant_engineer", "maintenance_manager", "procurement", "founder"],
            "buyer_types": ["TECHNICAL_BUYER", "ECONOMIC_BUYER", "CHAMPION"],
            "priority": ["engineering_manager", "plant_engineer", "maintenance_manager", "procurement", "founder"],
        },
        channels={"priority": ["email", "linkedin", "phone"]},
        qualification={
            "questions": [
                "A necessidade é detalhamento para fabricação, atualização documental ou engenharia reversa?",
                "Existe peça física, desenho antigo ou referência disponível?",
                "Qual o prazo e o impacto da falta desse desenho para fabricação ou manutenção?",
            ],
            "quality_gates": {
                "strong_evidence_any": ["CUSTOM_PARTS", "REVERSE_ENGINEERING", "CUSTOM_MANUFACTURING", "USINAGEM", "REPLACEMENT_PARTS"],
                "min_observed_signals": 2,
                "max_score_without_strong_evidence": 56,
                "max_score_with_sparse_evidence": 50,
                "high_confidence_score": 79,
            },
        },
        outreach={"angle": "desenho_para_fabricacao_ou_reposicao", "evidence_requirements": ["CUSTOM_PARTS", "REVERSE_ENGINEERING", "REPLACEMENT_PARTS"]},
    )

    _enhance(
        registry,
        "machine_manual",
        icp={
            "segments": ["fabricantes de máquinas", "integradores", "automação industrial", "indústria com frota de equipamentos"],
            "exclusions": ["varejo", "empresa sem máquinas ou equipamentos industriais"],
        },
        discovery={
            "providers": ["cnae_discovery", "google_places", "company_news", "job_search"],
            "target_candidates": 200,
            "provider_budgets": {"cnae_discovery": 90, "google_places": 60, "company_news": 30, "job_search": 20},
            "query_strategy": "machine-manufacturer+nr12+new-machine+region",
        },
        prescoring={
            "weights": {"MACHINE_MANUFACTURER": 28, "NEW_MACHINE": 26, "NR12": 30, "TECHNICAL_DOCUMENTATION": 26, "INDUSTRIAL_SAFETY": 18, "HAS_CNPJ": 8},
            "threshold": 38,
            "top_k": 30,
            "on_insufficient_data": "review",
        },
        enrichment={
            "steps": ["cnpj_receita", "business_social"],
            "max_cost": 4,
            "people_discovery": {"max_cost": 3, "max_steps": 3, "min_role_fit": 72},
        },
        signals={
            "positive": ["MACHINE_MANUFACTURER", "NEW_MACHINE", "NR12", "TECHNICAL_DOCUMENTATION", "INDUSTRIAL_SAFETY"],
            "negative": ["RETAIL_FOCUSED", "SERVICE_ONLY"],
            "weights": {"MACHINE_MANUFACTURER": 1.35, "NEW_MACHINE": 1.4, "NR12": 1.6, "TECHNICAL_DOCUMENTATION": 1.45, "INDUSTRIAL_SAFETY": 1.15},
            "negative_penalty_each": 22,
        },
        intent={
            "event_weights": {"NEW_MACHINE": 0.95, "NR12": 0.9, "TECHNICAL_DOCUMENTATION": 0.85, "NEW_EQUIPMENT": 0.75},
            "decay_days": 100,
            "trigger_threshold": 0.4,
        },
        decision_makers={
            "roles": ["engineering_manager", "safety_manager", "plant_engineer", "operations_director", "maintenance_manager", "procurement"],
            "buyer_types": ["TECHNICAL_BUYER", "ECONOMIC_BUYER", "CHAMPION"],
            "priority": ["engineering_manager", "safety_manager", "plant_engineer", "operations_director", "procurement"],
        },
        channels={"priority": ["email", "linkedin", "phone"]},
        qualification={
            "questions": [
                "A máquina é nova, será entregue ou precisa ter documentação atualizada?",
                "Existe manual técnico atual e ele cobre operação, manutenção e segurança?",
                "Há demanda de adequação ou evidência relacionada à NR-12?",
                "Quantas máquinas/modelos entram no escopo e qual é o prazo?",
            ],
            "quality_gates": {
                "strong_evidence_any": ["MACHINE_MANUFACTURER", "NEW_MACHINE", "NR12", "TECHNICAL_DOCUMENTATION"],
                "min_observed_signals": 2,
                "max_score_without_strong_evidence": 56,
                "max_score_with_sparse_evidence": 50,
                "high_confidence_score": 79,
            },
        },
        outreach={"angle": "documentacao_de_maquina_com_timing", "evidence_requirements": ["MACHINE_MANUFACTURER", "NEW_MACHINE", "NR12", "TECHNICAL_DOCUMENTATION"]},
    )

    _enhance(
        registry,
        "trophies",
        icp={
            "segments": ["eventos esportivos", "eventos corporativos", "federações", "associações", "premiações", "empresas juniores"],
            "exclusions": ["revenda exclusivamente online sem evento próprio"],
        },
        enrichment={
            "steps": ["business_social"],
            "max_cost": 4,
            "people_discovery": {"max_cost": 3, "max_steps": 3, "min_role_fit": 68},
        },
        signals={
            "positive": ["EVENT_SCHEDULED", "HOSTS_EVENTS", "SEASONAL_DEMAND", "CUSTOM_PRODUCTS", "HAS_INSTAGRAM"],
            "negative": ["ONLINE_ONLY_RESALE"],
            "weights": {"EVENT_SCHEDULED": 1.75, "HOSTS_EVENTS": 1.5, "SEASONAL_DEMAND": 1.3, "CUSTOM_PRODUCTS": 1.15, "HAS_INSTAGRAM": 0.65},
            "negative_penalty_each": 28,
        },
        decision_makers={
            "roles": ["event_manager", "marketing_director", "procurement", "founder", "commercial_director"],
            "priority": ["event_manager", "procurement", "commercial_director", "founder", "marketing_director"],
        },
        qualification={
            "questions": [
                "Qual é o evento, cerimônia ou competição e quando acontece?",
                "Quantas categorias, equipes ou reconhecimentos serão premiados?",
                "Quem aprova fornecedor, orçamento e personalização?",
                "Existe histórico ou recorrência dessa premiação?",
            ],
            "quality_gates": {
                "strong_evidence_any": ["EVENT_SCHEDULED", "HOSTS_EVENTS", "SEASONAL_DEMAND"],
                "min_observed_signals": 2,
                "max_score_without_strong_evidence": 52,
                "max_score_with_sparse_evidence": 48,
                "high_confidence_score": 78,
            },
        },
        outreach={"angle": "evento_com_janela_de_compra", "evidence_requirements": ["EVENT_SCHEDULED", "HOSTS_EVENTS"]},
    )

    _enhance(
        registry,
        "3d_printing",
        icp={"exclusions": ["varejo sem desenvolvimento de produto", "demanda exclusiva por produção seriada de alto volume"]},
        signals={
            "negative": ["RETAIL_FOCUSED"],
            "negative_penalty_each": 20,
            "weights": {"NEW_PRODUCT": 1.25, "PROTOTYPE": 1.5, "R_AND_D": 1.35, "CUSTOM_PARTS": 1.15},
        },
        qualification={
            "questions": [
                "O objetivo é validar um conceito, produzir um protótipo funcional ou fabricar uma peça final?",
                "Qual material, dimensão, quantidade e prazo são necessários?",
                "Existe modelo 3D pronto ou será preciso apoiar o desenvolvimento?",
            ],
            "quality_gates": {
                "strong_evidence_any": ["PROTOTYPE", "R_AND_D", "NEW_PRODUCT", "CUSTOM_PARTS"],
                "min_observed_signals": 1,
                "max_score_without_strong_evidence": 56,
                "high_confidence_score": 80,
            },
        },
    )

    _enhance(
        registry,
        "laser_cutting_technical",
        icp={"exclusions": ["varejo sem demanda técnica", "serviço sem necessidade de fabricação"]},
        signals={
            "negative": ["RETAIL_FOCUSED", "SERVICE_ONLY"],
            "negative_penalty_each": 20,
            "weights": {"CUSTOM_PARTS": 1.4, "USINAGEM": 1.0, "CUSTOM_MANUFACTURING": 1.3, "NEW_EQUIPMENT": 1.1},
        },
        qualification={
            "questions": [
                "Qual peça ou chapa precisa ser cortada e em qual material/espessura?",
                "Existe desenho técnico ou arquivo de fabricação disponível?",
                "Qual quantidade, tolerância e prazo de entrega?",
            ],
            "quality_gates": {
                "strong_evidence_any": ["CUSTOM_PARTS", "CUSTOM_MANUFACTURING", "USINAGEM"],
                "min_observed_signals": 1,
                "max_score_without_strong_evidence": 56,
                "high_confidence_score": 80,
            },
        },
    )

    _enhance(
        registry,
        "laser_custom_products",
        icp={"exclusions": ["revenda genérica sem personalização ou evento"]},
        signals={
            "negative": ["ONLINE_ONLY_RESALE"],
            "negative_penalty_each": 24,
            "weights": {"EVENT_SCHEDULED": 1.5, "SEASONAL_DEMAND": 1.25, "HAS_INSTAGRAM": 0.65, "CUSTOM_PRODUCTS": 1.35},
        },
        qualification={
            "questions": [
                "Qual produto será personalizado e para qual ocasião ou público?",
                "Qual quantidade, material e nível de personalização são necessários?",
                "Existe uma data de evento ou prazo de entrega definido?",
            ],
            "quality_gates": {
                "strong_evidence_any": ["EVENT_SCHEDULED", "CUSTOM_PRODUCTS", "SEASONAL_DEMAND"],
                "min_observed_signals": 1,
                "max_score_without_strong_evidence": 55,
                "high_confidence_score": 79,
            },
        },
    )

    # Sinais de fit primários representam necessidade comercial. CNPJ, telefone
    # e e-mail ajudam na execução, mas não devem ser a razão principal do fit.
    _set_signal_roles(
        registry,
        "mechanical_project",
        positive=["HAS_PRODUCTION_LINE", "CUSTOM_MACHINERY", "AUTOMATION", "EXPANDING_FACTORY", "NEW_EQUIPMENT", "HIRING_MECHANICAL_ENGINEER"],
        optional_positive=["HAS_CNPJ", "HAS_BUSINESS_EMAIL", "HAS_PHONE"],
        negative=["RETAIL_FOCUSED", "SERVICE_ONLY"],
    )
    _set_signal_roles(
        registry,
        "technical_drawing",
        positive=["CUSTOM_PARTS", "REVERSE_ENGINEERING", "CUSTOM_MANUFACTURING", "USINAGEM", "REPLACEMENT_PARTS"],
        optional_positive=["HAS_CNPJ", "HAS_BUSINESS_EMAIL", "HAS_PHONE"],
        negative=["RETAIL_FOCUSED", "SERVICE_ONLY"],
    )
    _set_signal_roles(
        registry,
        "machine_manual",
        positive=["MACHINE_MANUFACTURER", "NEW_MACHINE", "NR12", "TECHNICAL_DOCUMENTATION", "INDUSTRIAL_SAFETY"],
        optional_positive=["HAS_CNPJ", "HAS_BUSINESS_EMAIL", "HAS_PHONE"],
        negative=["RETAIL_FOCUSED", "SERVICE_ONLY"],
    )
    _set_signal_roles(
        registry,
        "trophies",
        positive=["EVENT_SCHEDULED", "HOSTS_EVENTS", "SEASONAL_DEMAND", "CUSTOM_PRODUCTS"],
        optional_positive=["HAS_INSTAGRAM", "HAS_PHONE"],
        negative=["ONLINE_ONLY_RESALE"],
    )

    for key in ("trophies_sports", "trophies_mej"):
        _enhance(
            registry,
            key,
            qualification={
                "quality_gates": {
                    "min_observed_signals": 2,
                    "max_score_with_sparse_evidence": 48,
                }
            },
        )

    return registry
