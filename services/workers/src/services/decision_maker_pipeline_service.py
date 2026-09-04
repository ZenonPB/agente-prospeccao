"""Decision Maker Resolution Pipeline (#34) — unifica o caminho empresa→decisor.

Seam: lead_data + profile → TargetRoleResolver → Identity → Contact → DecisionMakerScore.
Orquestrador único com cascata explícita (doc #44) e auditabilidade.
"""
from typing import Any, Dict, List, Optional
from services.decision_maker_strategy_service import resolve_contact_strategy
from services.chain_detection_service import detect_chain
from services.prospecting_profile_service import resolve_prospecting_profile


def resolve_target_roles(profile_key: str, offer_context: Optional[Dict] = None) -> List[Dict]:
    """Resolve cargos-alvo por vertical (ECONOMIC/TECHNICAL/CHAMPION)."""
    roles_by_profile = {
        "web_presence": ["marketing_manager", "founder", "product_manager"],
        "business_opportunity": ["procurement_manager", "operations_director", "ceo"],
        "industrial": ["plant_engineer", "maintenance_manager", "operations_director"],
        "generic": ["decision_maker", "manager"],
    }
    roles = roles_by_profile.get(profile_key, roles_by_profile["generic"])
    return [{"role": r, "buyer_type": _buyer_type(r)} for r in roles]


def _buyer_type(role: str) -> str:
    if any(k in role for k in ["procurement", "operations", "plant", "maintenance"]):
        return "TECHNICAL_BUYER"
    if any(k in role for k in ["ceo", "founder", "director"]):
        return "ECONOMIC_BUYER"
    return "CHAMPION"


def run_decision_maker_pipeline(lead_data: Dict, profile: Dict) -> Dict[str, Any]:
    """Pipeline completo (#34): target roles → chain detection → contact strategy."""
    profile_key = profile.get("profile_key", "generic")
    strategy = resolve_contact_strategy(profile_key)
    chain = detect_chain(lead_data)
    roles = resolve_target_roles(profile_key)

    # Evidência de acessibilidade do decisor (#14)
    accessibility_evidence = chain.get("evidence", [])

    return {
        "profile_key": profile_key,
        "target_roles": roles,
        "chain_classification": chain.get("classification"),
        "chain_confidence": chain.get("confidence"),
        "contact_strategy": strategy,
        "decision_maker_accessibility": {
            "score": 70 if roles else 30,
            "evidence": accessibility_evidence,
            "accessible": len(roles) > 0,
        },
        "source": "decision_maker_pipeline_service",
    }
