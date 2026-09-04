"""Prospecting Hypothesis (#28) — hipótese de prospecção declarativa.

Seam: ProspectingProfile → ProspectingHypothesis (problem/hypothesis/expected_lift).
Define a HIPÓTESE de valor antes de enriquecer — direciona o que o pipeline coleta.
"""
from typing import Any, Dict, Optional
from services.prospecting_profile_service import (
    PROFILE_WEB_PRESENCE, PROFILE_BUSINESS, PROFILE_INDUSTRIAL,
)

_HYPOTHESIS_BASE: Dict[str, Dict[str, Any]] = {
    PROFILE_WEB_PRESENCE: {
        "problem": "Leads sem presença digital ou com presença fraca perdem conversão.",
        "hypothesis": "Oferecer desenvolvimento de site/landing aumenta conversão em +40%.",
        "expected_lift": 0.40,
        "key_signals": ["NO_OWN_WEBSITE", "LOW_GOOGLE_RATING"],
    },
    PROFILE_BUSINESS: {
        "problem": "Empresas que não aparecem no B2B perdem oportunidades de mercado.",
        "hypothesis": "Visibilidade + presença corporativa bem posicionada gera +35% de leads.",
        "expected_lift": 0.35,
        "key_signals": ["HAS_OWN_WEBSITE_FALLBACK_INSTAGRAM", "LOW_GOOGLE_RATING_COUNT"],
    },
    PROFILE_INDUSTRIAL: {
        "problem": "Indústrias sem prospecção digital estruturada perdem contratos B2B relevantes.",
        "hypothesis": "Projeto mecânico / documentação técnica outbound qualificada gera +30% de consultas industriais.",
        "expected_lift": 0.30,
        "key_signals": ["HAS_CNPJ", "CNAE_INDUSTRIAL", "HIRING"],
    },
    "generic": {
        "problem": "Ausência de prospecção direcionada reduz taxa de resposta.",
        "hypothesis": "Contato direcionado a decisão + valor claro aumenta resposta em +25%.",
        "expected_lift": 0.25,
        "key_signals": ["NO_PHONE", "NO_GOOGLE_RATING"],
    },
}


def build_hypothesis(profile_key: str, lead_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Monta a hipótese de prospecção para o perfil + contexto do lead."""
    base = _HYPOTHESIS_BASE.get(profile_key, _HYPOTHESIS_BASE["generic"])
    return {
        "profile_key": profile_key,
        "problem": base["problem"],
        "hypothesis": base["hypothesis"],
        "expected_lift": base["expected_lift"],
        "key_signals": base["key_signals"],
        "lead_context": lead_context or {},
        "source": "prospecting_hypothesis_service",
    }


def vertical_pack_for(profile_key: str) -> Dict[str, Any]:
    """Vertical Pack (#31) — agrupa providers específicos de enriquecimento.

    Diz quais providers executar em pré-ordem para este perfil.
    """
    packs = {
        PROFILE_WEB_PRESENCE: ["google_places", "discovery_multi_query", "technical_enrichment"],
        PROFILE_BUSINESS:     ["cnpj_discovery", "business_social", "cnpj_qsa"],
        PROFILE_INDUSTRIAL:   ["cnae_discovery", "cnpj_receita", "site_contact_pages"],
        "generic":            ["google_places", "discovery_multi_query"],
    }
    providers = packs.get(profile_key, packs["generic"])
    return {
        "profile_key": profile_key,
        "enrichment_pack": providers,
        "source": "prospecting_hypothesis_service.vertical_pack_for",
    }
