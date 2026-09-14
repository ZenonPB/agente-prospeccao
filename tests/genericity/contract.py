"""Contrato executável das capabilities genéricas.

Uma capability sob contrato é uma única implementação usada pelas verticais,
recebe diferenças por OfferProfile e produz o mesmo formato de saída. Os leads
ideais abaixo refletem os Golden Paths de produção, em vez de fixtures legadas.
"""
from typing import Any, Dict, List

from services.prospecting.offer_profile import OfferProfile

from genericity.profiles import ENGINEERING_KEY, TROPHIES_KEY, WEB_ERP_KEY

IDEAL_LEADS: Dict[str, Dict[str, Any]] = {
    TROPHIES_KEY: {
        "hosts_events": True,
        "event_scheduled": True,
        "has_instagram": True,
        "seasonal_demand": True,
        "segment": "eventos",
    },
    WEB_ERP_KEY: {
        "manual_process": True,
        "uses_spreadsheets": True,
        "multi_unit": True,
        "expanding": True,
        "segment": "distribuição",
        "company_size": "EPP",
    },
    ENGINEERING_KEY: {
        "has_cnpj": True,
        "has_business_email": True,
        "has_phone": True,
        "has_production_line": True,
        "expanding_factory": True,
        "new_equipment": True,
        "segment": "metalúrgica",
        "cnae": "2599-3/99",
        "company_size": "ME",
    },
}


def ideal_lead(key: str) -> Dict[str, Any]:
    return dict(IDEAL_LEADS[key])


def disqualified_lead(profile: OfferProfile) -> Dict[str, Any] | None:
    """Lead ideal com desqualificador, quando a oferta declara um.

    Nem toda oferta deve possuir desqualificador binário: alguns contra-sinais
    são penalidades graduais. O harness não força semântica comercial falsa só
    para satisfazer um teste estrutural.
    """
    disqualifiers = (profile.signals or {}).get("disqualifiers") or []
    if not disqualifiers:
        return None
    lead = ideal_lead(profile.key)
    lead[disqualifiers[0].lower()] = True
    return lead


def discovery_plan_from_profile(profile: OfferProfile) -> Dict[str, Any]:
    discovery = profile.discovery or {}
    budgets = discovery.get("provider_budgets") or {}
    providers = [
        {"type": name, "queries": ["base"], "budget": int(budgets.get(name, 50))}
        for name in discovery.get("providers") or []
    ]
    plan: Dict[str, Any] = {"providers": providers}
    target = discovery.get("target_candidates")
    if target is not None:
        plan["target_candidates"] = int(target)
    return plan


def declared_providers(profile: OfferProfile) -> List[str]:
    return list((profile.discovery or {}).get("providers") or [])


def intent_config(profile: OfferProfile) -> Dict[str, Any]:
    intent = profile.intent or {}
    return {
        "decay_days": int(intent.get("decay_days", 90)),
        "trigger_threshold": float(intent.get("trigger_threshold", 0.5)),
    }


OPPORTUNITY_KEYS = frozenset({
    "offer_key", "profile_key", "score", "offer_version", "evidence",
    "resolved_from", "signals_matched", "signals_missing", "score_breakdown",
})
INTENT_SCORE_KEYS = frozenset({"key", "score", "triggered", "reason"})
NEXT_ACTION_KEYS = frozenset({
    "action", "why", "confidence", "evidence", "deadline", "priority",
})
DISCOVERY_RESULT_KEYS = frozenset({
    "results_by_provider", "execution_order", "skipped", "total_candidates",
    "unique_candidates", "unique_count", "budget_used",
})
