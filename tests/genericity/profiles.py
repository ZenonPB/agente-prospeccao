"""Fixtures de OfferProfile do Genericity Test Harness (Task 2).

Três perfis compõem o contrato, escolhidos como testes arquiteturais opostos:

- ``trophies``  — vertical dirigida por evento/timing/recorrência (produção);
- ``web_erp``   — vertical dirigida por complexidade operacional (fixture);
- ``mechanical_project`` — Engenharia Mecânica, prova de configurabilidade
  teórica sem implementação vertical dedicada (produção).

Troféus e Engenharia vêm do **registry de produção**: o harness exercita o core
real, não um clone. ``web_erp`` é fixture porque a vertical de Sistemas Web/ERP
só é implementada na Task 8 — promover um perfil incompleto para
``default_profiles`` agora criaria configuração órfã.

O perfil de fixture usa apenas sinais já presentes no Signal Registry, para
validar no mesmo padrão dos perfis de produção.
"""
from typing import Dict, List

from services.prospecting.default_profiles import get_default_registry
from services.prospecting.offer_profile import OfferProfile, OfferProfileRegistry

# Chaves do contrato. `web_erp` é fixture; as outras duas são de produção.
TROPHIES_KEY = "trophies"
WEB_ERP_KEY = "web_erp"
ENGINEERING_KEY = "mechanical_project"

# Chaves esperadas no registry de produção (o harness falha se desaparecerem).
PRODUCTION_KEYS = (TROPHIES_KEY, ENGINEERING_KEY)

CONTRACT_KEYS = (TROPHIES_KEY, WEB_ERP_KEY, ENGINEERING_KEY)


def build_web_erp_fixture() -> OfferProfile:
    """Perfil de Sistemas Web/ERP usado como segundo piloto do contrato.

    Representa a pergunta comercial da vertical ("a operação já está complexa
    o suficiente para justificar uma solução personalizada?") com os sinais
    disponíveis hoje. A Task 8 substitui isto por technographics e sinais de
    complexidade reais — aqui basta ser uma configuração válida e oposta à de
    Troféus (sem timing de evento, com firmographics e intent de crescimento).
    """
    return OfferProfile(
        key=WEB_ERP_KEY,
        archetype="operations_software",
        vertical="business_systems",
        version="1.0",
        offer={
            "name": "Sistema Web/ERP sob medida",
            "tagline": "Sistema próprio para operação complexa",
        },
        icp={
            "company_sizes": ["EPP", "ME"],
            "segments": ["distribuidora", "logística", "indústria"],
            "cnaes": ["46", "47", "49"],
            "exclusions": ["software house", "SaaS"],
            "geography": {"country": "BR"},
        },
        discovery={
            "providers": ["cnae_discovery", "google_places"],
            "target_candidates": 200,
            "provider_budgets": {"cnae_discovery": 120, "google_places": 80},
            "query_strategy": "cnae+city",
        },
        prescoring={
            "required_signals": ["HAS_CNPJ"],
            "weights": {
                "HAS_CNPJ": 20, "HAS_BUSINESS_EMAIL": 10,
                "HIRING": 15, "NEW_BRANCH": 15,
            },
            "threshold": 45,
            "top_k": 30,
            # Complexidade operacional raramente é observável na descoberta:
            # falta de evidência vai para revisão, não para descarte.
            "on_insufficient_data": "review",
        },
        enrichment={
            "steps": ["cnpj_receita", "technical_site"],
            "max_cost": 4,
            "people_discovery": {"max_cost": 2, "max_steps": 2, "min_role_fit": 70},
        },
        signals={
            "positive": ["HAS_CNPJ", "HIRING", "NEW_BRANCH", "HAS_BUSINESS_EMAIL"],
            # Crescimento/expansão pesa mais que formalidade: o gatilho da
            # oferta é a operação crescendo, não a empresa existir.
            "weights": {
                "HAS_CNPJ": 10, "HIRING": 15,
                "NEW_BRANCH": 20, "HAS_BUSINESS_EMAIL": 8,
            },
            "negative": ["ONLINE_ONLY_RESALE"],
            # Portal próprio maduro = a dor já foi resolvida internamente.
            "disqualifiers": ["HAS_CUSTOMER_PORTAL"],
        },
        intent={
            "event_weights": {"HIRING": 0.8, "EXPANDING": 0.7, "NEW_BRANCH": 0.9},
            # Ciclo longo: o oposto de Troféus, cuja janela é curta.
            "decay_days": 120,
            "trigger_threshold": 0.5,
        },
        decision_makers={
            "roles": ["founder", "operations_director", "it_manager", "finance_manager"],
            "buyer_types": ["ECONOMIC_BUYER", "TECHNICAL_BUYER"],
            "priority": ["founder", "operations_director", "it_manager"],
        },
        channels={"priority": ["email", "linkedin", "phone"]},
        qualification={
            "questions": [
                "Quantos sistemas/planilhas sustentam a operação hoje?",
                "Estoque, vendas e financeiro conversam entre si?",
                "Quantas unidades/filiais operam?",
            ],
        },
        outreach={
            "angle": "complexidade_operacional",
            "evidence_requirements": ["HAS_CNPJ", "HIRING"],
        },
    )


def production_profile(key: str) -> OfferProfile:
    """Devolve um perfil do registry de produção, falhando alto se ausente."""
    profile = get_default_registry().get(key)
    if profile is None:
        raise AssertionError(
            f"OfferProfile de produção {key!r} ausente do registry padrão — "
            "o Genericity Harness depende dele."
        )
    return profile


def contract_profiles() -> Dict[str, OfferProfile]:
    """Mapa ``key -> OfferProfile`` das três verticais do contrato."""
    return {
        TROPHIES_KEY: production_profile(TROPHIES_KEY),
        WEB_ERP_KEY: build_web_erp_fixture(),
        ENGINEERING_KEY: production_profile(ENGINEERING_KEY),
    }


def contract_registry() -> OfferProfileRegistry:
    """Registry isolado com apenas os três perfis do contrato.

    Isolar evita que perfis adicionais de produção tornem as asserções de
    ranqueamento não determinísticas.
    """
    registry = OfferProfileRegistry()
    for profile in contract_profiles().values():
        registry.register(profile)
    return registry


def contract_keys() -> List[str]:
    """Chaves do contrato, em ordem estável."""
    return list(CONTRACT_KEYS)
