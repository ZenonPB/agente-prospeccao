"""Contrato executável das capabilities genéricas (Task 2).

Uma capability sob contrato:

1. é **uma só implementação** usada pelas três verticais;
2. recebe a diferença de comportamento por **configuração** (OfferProfile),
   nunca por branch de vertical no core;
3. produz saída com **o mesmo formato** para qualquer vertical;
4. é configurável para Engenharia Mecânica sem implementação dedicada.

Este módulo concentra os dados de entrada por vertical e os adaptadores que
derivam entradas de serviço a partir do OfferProfile, para que os testes
comparem verticais sem repetir setup.
"""
from typing import Any, Dict, List

from services.prospecting.offer_profile import OfferProfile

from genericity.profiles import ENGINEERING_KEY, TROPHIES_KEY, WEB_ERP_KEY

# Lead que representa o "encaixe ideal" de cada vertical. As chaves seguem a
# convenção do OfferMatcher (`HAS_X` presente <=> lead["has_x"] is True).
IDEAL_LEADS: Dict[str, Dict[str, Any]] = {
    # Timing/evento: o que qualifica é existir evento e canal social.
    TROPHIES_KEY: {
        "hosts_events": True,
        "has_instagram": True,
        "segment": "eventos",
    },
    # Complexidade/crescimento: firmographics + sinais de expansão.
    WEB_ERP_KEY: {
        "has_cnpj": True,
        "hiring": True,
        "new_branch": True,
        "has_business_email": True,
        "segment": "distribuidora",
        "cnae": "4649-4/99",
        "company_size": "EPP",
    },
    # Capacidade industrial instalada.
    ENGINEERING_KEY: {
        "has_cnpj": True,
        "has_business_email": True,
        "has_phone": True,
        "segment": "metalúrgica",
        "cnae": "2599-3/99",
        "company_size": "ME",
    },
}


def ideal_lead(key: str) -> Dict[str, Any]:
    """Lead de encaixe ideal para a vertical (cópia, para não vazar estado)."""
    return dict(IDEAL_LEADS[key])


def disqualified_lead(profile: OfferProfile) -> Dict[str, Any]:
    """Lead ideal acrescido do primeiro desqualificador declarado pelo perfil.

    Permite testar o caminho de desqualificação sem o teste conhecer qual é o
    sinal de cada vertical — ele vem da configuração.
    """
    disqualifiers = (profile.signals or {}).get("disqualifiers") or []
    if not disqualifiers:
        raise AssertionError(
            f"perfil {profile.key!r} não declara disqualifiers — "
            "o contrato exige ao menos um para cobrir a desqualificação."
        )
    lead = ideal_lead(profile.key)
    lead[disqualifiers[0].lower()] = True
    return lead


def discovery_plan_from_profile(profile: OfferProfile) -> Dict[str, Any]:
    """Deriva um plano de discovery **apenas** da seção ``discovery`` do perfil.

    Este é o contrato-alvo: nenhuma decisão vem do nome da vertical. A Task 5
    move esta derivação para o core (hoje ``discovery_planner_service`` ainda
    ramifica por ``profile_key``; ver ``core_purity.KNOWN_VIOLATIONS``).
    """
    discovery = profile.discovery or {}
    budgets = discovery.get("provider_budgets") or {}
    providers = [
        {
            "type": name,
            "queries": ["base"],
            "budget": int(budgets.get(name, 50)),
        }
        for name in discovery.get("providers") or []
    ]
    plan: Dict[str, Any] = {"providers": providers}
    target = discovery.get("target_candidates")
    if target is not None:
        plan["target_candidates"] = int(target)
    return plan


def declared_providers(profile: OfferProfile) -> List[str]:
    """Providers de discovery declarados pelo perfil, em ordem."""
    return list((profile.discovery or {}).get("providers") or [])


def intent_config(profile: OfferProfile) -> Dict[str, Any]:
    """Parâmetros de intent do perfil, com defaults explícitos do motor."""
    intent = profile.intent or {}
    return {
        "decay_days": int(intent.get("decay_days", 90)),
        "trigger_threshold": float(intent.get("trigger_threshold", 0.5)),
    }


# Formato mínimo de saída por capability. O contrato exige que a saída tenha as
# mesmas chaves para todas as verticais — valores podem (e devem) divergir.
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
