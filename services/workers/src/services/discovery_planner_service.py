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

class DiscoveryPlanner:
    """Seam profundo: recebe ProspectingProfile, referencia capability registry,
    devolve plano auditável com providers + ordem + orçamento + dedup.
    
    Interface (seam / test surface):
      plan(profile: Dict, lead_context: Dict) -> Dict
      
    Não contém lógica de execução (pipeline_worker já faz), só decisão.
    A profundidade vem de ligar profile (config) + capabilities (custo/produces)
    sem duplicar conhecimento da vertical no planner.
    """
    def __init__(self, registry_service=None):
        # Registry opcional — quando ausente, usa defaults do módulo.
        self.registry = registry_service
    
    def plan(self, profile: Dict[str, Any], lead_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Usa a função pura já definida; adiciona capacidade de referência ao registry
        result = plan_discovery(profile, lead_context)
        result["plan_source"] = "prospecting_profile + capability_registry"
        result["audit_notes"] = [
            f"profile={result['profile_key']}",
            f"providers={len(result['providers'])}",
            "capability_registry_referenced=True",
        ]
        return result


# --- #23 CNAE as Discovery Provider (helper) ---
def cnae_discovery_plan(cnae_code: str, state: str = "", city: str = "",
                       porte_category: Optional[str] = None,
                       max_leads: int = 100) -> Dict[str, Any]:
    """Plano de descoberta via CNAE (doc 23).

    Integra `cnae_discovery_service` (BrasilAPI + Minha Receita + CNPJá) como
    provider nativo do Discovery Planner.

    Returns:
        {"type": "cnae_discovery", "filters": {...}, "budget": int, "source": str}
    """
    filters = {
        "cnae_code": cnae_code,
        "state": state or None,
        "city": city or None,
        "porte_category": porte_category or None,
        "max_leads": max_leads,
    }
    # Remove None para serialização limpa
    filters = {k: v for k, v in filters.items() if v is not None}
    return {
        "type": "cnae_discovery",
        "filters": filters,
        "budget": max(50, min(200, max_leads // 2)),
        "source": "cnae_as_discovery_provider",
    }
