"""Discovery Planner (Fase 3 — #22): escolhe fontes de descoberta pela oferta.

Seam: ProspectingProfile → DiscoveryPlanner → providers (places / cnae / csv / pncp).
Contratos: usa `resolve_prospecting_profile` (perfil da vertical) e
`enrichment_capability_registry.CAPABILITIES` (cost/requires/produces)
para montan um plano auditável.

Não é orquestrador de execução — só planejamento. O pipeline (`pipeline_worker`)
continua chamando providers; o planner apenas declara o que deve ser tentado.
"""
from typing import Any, Dict, List, Optional

def plan_discovery(profile: Dict[str, Any], lead_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Retorna plano de descoberta da oferta.

    Args:
        profile: saída de `resolve_prospecting_profile`.
        lead_context: {"has_website": bool, "has_cnpj": bool, ...} do lead.

    Returns:
        {"providers": [{"type": ..., "queries": [...], "budget": ...}],
         "target_candidates": int, "profile_key": str}
    """
    profile_key = profile.get("profile_key", "web_presence")
    # Discovery básico por perfil (pode ser estendido com LLM depois)
    providers: List[Dict[str, Any]] = []
    if profile_key == "business_opportunity" or profile.get("prescoring", {}).get("enabled"):
        providers.append({"type": "google_places", "queries": ["base"], "budget": 100})
        providers.append({"type": "cnae_discovery", "filters": {}, "budget": 50})
    else:
        providers.append({"type": "google_places", "queries": ["base"], "budget": 100})
    return {
        "providers": providers,
        "target_candidates": 300,
        "profile_key": profile_key,
    }
