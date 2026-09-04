"""Routable Contact (#42) + Actionable Contact Rate (#47).

#42: modela DIRECT_CONTACT vs ROUTABLE_CONTACT (PABX + target_person).
#47: métrica consolidada que distingue direct/routable/institutional.
"""
from typing import Any, Dict, List, Optional


def classify_routability(phone: Optional[str], pabx_extension: Optional[str] = None,
                          target_person: Optional[str] = None) -> Dict[str, Any]:
    """Classifica contato em DIRECT/ROUTABLE/INSTITUTIONAL.

    DIRECT: telefone direto da pessoa (sem PABX).
    ROUTABLE: telefone com PABX (exige extension + nome da pessoa).
    INSTITUTIONAL: telefone institucional genérico (não-routable).
    """
    if not phone:
        return {"type": "UNKNOWN", "routable": False, "reason": "no_phone"}
    if pabx_extension and target_person:
        return {"type": "ROUTABLE_CONTACT", "routable": True,
                "pabx_extension": pabx_extension, "target_person": target_person}
    # Heurística simples: telefones curtos ou genéricos = INSTITUTIONAL
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) <= 8:
        return {"type": "INSTITUTIONAL", "routable": False, "reason": "generic_short"}
    return {"type": "DIRECT_CONTACT", "routable": True, "reason": "direct_line"}


def actionable_contact_rate(contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Métrica consolidada (#47) — % de contatos acionáveis (direct + routable)."""
    if not contacts:
        return {"actionable_rate": 0.0, "total": 0, "direct": 0, "routable": 0, "institutional": 0}
    counts = {"DIRECT_CONTACT": 0, "ROUTABLE_CONTACT": 0, "INSTITUTIONAL": 0, "UNKNOWN": 0}
    for c in contacts:
        cls = classify_routability(
            c.get("phone"),
            pabx_extension=c.get("pabx_extension"),
            target_person=c.get("target_person") or c.get("full_name"),
        )
        counts[cls["type"]] = counts.get(cls["type"], 0) + 1
    actionable = counts["DIRECT_CONTACT"] + counts["ROUTABLE_CONTACT"]
    return {
        "actionable_rate": round(actionable / len(contacts), 3),
        "total": len(contacts),
        "direct": counts["DIRECT_CONTACT"],
        "routable": counts["ROUTABLE_CONTACT"],
        "institutional": counts["INSTITUTIONAL"],
        "unknown": counts["UNKNOWN"],
        "source": "routable_contact_service.actionable_contact_rate",
    }
