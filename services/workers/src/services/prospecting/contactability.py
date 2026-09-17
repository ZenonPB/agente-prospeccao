"""Classificação determinística de contatabilidade a partir de dados já observados.

Não executa providers nem inventa contatos. Ausência de evidência permanece UNKNOWN;
falha de provider é distinta de uma busca concluída sem resultado.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def _number(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return max(0.0, min(100.0, float(value or 0)))
    except (TypeError, ValueError):
        return 0.0


def _is_real_person(contact: Mapping[str, Any]) -> bool:
    name = str(contact.get("name") or "").strip().lower()
    return bool(name and name not in {"decisor", "contato", "comercial", "vendas"})


def assess_contactability(
    contacts: Iterable[Mapping[str, Any]] | None,
    *,
    discovery_status: str | None = None,
) -> dict[str, Any]:
    """Retorna score/status explicável sem confundir UNKNOWN com zero.

    O score representa capacidade de chegar a uma pessoa adequada, não fit da
    empresa. Contato direto verificado domina; canal genérico é útil, mas não
    equivale a decisor identificado. Falhas/disabled preservam UNKNOWN quando
    nenhum contato foi observado.
    """
    items = [item for item in (contacts or ()) if isinstance(item, Mapping)]
    provider_status = str(discovery_status or "").strip().lower() or None
    failed_states = {"failed", "error", "quota_exceeded", "budget_exceeded", "disabled"}

    if not items:
        if provider_status in failed_states:
            return {
                "score": None,
                "status": "UNKNOWN",
                "reason": f"people_discovery_{provider_status}",
                "person_found": False,
                "direct_contact": False,
                "verified_contact": False,
            }
        if provider_status in {"empty", "not_found"}:
            return {
                "score": 0,
                "status": "NO_CONTACT_FOUND",
                "reason": "people_discovery_completed_without_contact",
                "person_found": False,
                "direct_contact": False,
                "verified_contact": False,
            }
        return {
            "score": None,
            "status": "UNKNOWN",
            "reason": "contactability_not_observed",
            "person_found": False,
            "direct_contact": False,
            "verified_contact": False,
        }

    best: tuple[float, dict[str, Any]] | None = None
    for contact in items:
        real_person = _is_real_person(contact)
        email = bool(contact.get("email"))
        phone = bool(contact.get("phone"))
        linkedin = bool(contact.get("linkedin_url"))
        verified = bool(contact.get("email_verified")) or str(contact.get("verification_status") or "") == "fully_verified"
        routable = bool(contact.get("routable"))
        role_fit = _number((contact.get("raw_data") or {}).get("role_fit_score") if isinstance(contact.get("raw_data"), Mapping) else 0)
        confidence = max(_number(contact.get("contact_confidence")), _number(contact.get("confidence")))

        if real_person and verified and (email or phone):
            score, status, reason = max(85.0, confidence), "VERIFIED_DIRECT", "verified_direct_contact"
        elif real_person and routable and (email or phone):
            score, status, reason = max(75.0, confidence), "DIRECT", "routable_person_contact"
        elif real_person and (email or phone):
            score, status, reason = max(60.0, confidence), "DIRECT_NEEDS_VERIFICATION", "person_contact_needs_verification"
        elif real_person and linkedin:
            score, status, reason = max(45.0, confidence), "PERSON_CHANNEL", "person_found_with_assisted_channel"
        elif email or phone:
            score, status, reason = max(30.0, min(55.0, confidence)), "GENERIC_CHANNEL", "company_channel_without_confirmed_person"
        elif real_person:
            score, status, reason = max(20.0, min(40.0, confidence)), "PERSON_NO_CONTACT", "person_found_without_contact_channel"
        else:
            score, status, reason = 10.0, "PLACEHOLDER", "placeholder_without_confirmed_person"

        if role_fit >= 70 and real_person:
            score = min(100.0, score + 5.0)
        payload = {
            "score": round(score),
            "status": status,
            "reason": reason,
            "person_found": real_person,
            "direct_contact": real_person and (email or phone),
            "verified_contact": real_person and verified and (email or phone),
        }
        if best is None or score > best[0]:
            best = (score, payload)

    return best[1]
