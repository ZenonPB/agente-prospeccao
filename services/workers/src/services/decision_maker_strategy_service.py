"""Decision Maker Strategy (#25) — estratégia ordenada de contato por perfil.

Seam: ProspectingProfile (profile_key) → DecisionMakerStrategy (channel order).
Não toma ação — apenas declara a ordem de providers para resolução de identity
+ contato. Ordem declarativa; cada provider é stateless e é chamado pelo
orquestrador de contato.

Perfis suportados: web_presence, business_opportunity, industrial, generic.
Adicionar vertical = adicionar entry aqui + (eventualmente) no profile registry.
"""
from typing import Any, Dict, List
from services.prospecting_profile_service import (
    PROFILE_WEB_PRESENCE, PROFILE_BUSINESS, PROFILE_INDUSTRIAL,
)

# Estratégia de providers ordenados por perfil.
# Cada provider tem prioridade; parada-stop_after controla quantos rodam.
STRATEGY_BY_PROFILE: Dict[str, List[str]] = {
    PROFILE_WEB_PRESENCE:        ["domain_first_person", "linkedin_search", "email_pattern_inference"],
    PROFILE_BUSINESS:            ["cnpj_qsa", "domain_first_person", "email_pattern_inference"],
    PROFILE_INDUSTRIAL:          ["cnpj_qsa", "site_contact_pages", "email_pattern_inference"],
    # fallback genérico — mais conservador, prioriza LinkedIn (mais dados públicos)
    "generic":                   ["linkedin_search", "domain_first_person", "email_pattern_inference"],
}

# Prioridade de canais de contato (onde achamos/mensagem) — usado pelo roster.
CHANNEL_PRIORITY_BY_PROFILE: Dict[str, List[str]] = {
    PROFILE_WEB_PRESENCE:        ["email", "linkedin", "phone"],
    PROFILE_BUSINESS:            ["email", "phone", "linkedin"],
    PROFILE_INDUSTRIAL:          ["email", "phone", "linkedin"],
    "generic":                   ["email", "linkedin", "phone"],
}


def resolve_contact_strategy(profile_key: str) -> Dict[str, Any]:
    """Devolve a estratégia de contact-maker para o perfil.

    Returns:
        {
            "profile_key": str,
            "provider_order": List[str],       # providers de identity/contato
            "channel_priority": List[str],   # onde tentar outreach
            "stop_after": int,               # para evitar escanear tudo
            "source": "decision_maker_strategy_service",
        }
    """
    strategy = STRATEGY_BY_PROFILE.get(profile_key, STRATEGY_BY_PROFILE["generic"])
    channels = CHANNEL_PRIORITY_BY_PROFILE.get(profile_key, CHANNEL_PRIORITY_BY_PROFILE["generic"])
    return {
        "profile_key": profile_key,
        "provider_order": list(strategy),
        "channel_priority": list(channels),
        "stop_after": min(len(strategy), 2),  # padrão: resolve rápido
        "source": "decision_maker_strategy_service",
    }
