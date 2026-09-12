"""Pontuação determinística de acionabilidade de um contato.

A pontuação resume qualidade de identidade, aderência ao papel, contato e
atualidade sem esconder ausência de evidência. Dimensões sem dado permanecem
``unknown`` no breakdown; o score numérico é conservador para ordenação, mas a
API/UI consegue distinguir zero observado de informação inexistente.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from services.prospecting.buyer_persona import match_persona_for_role


_WEIGHTS = {
    "identity_confidence": 0.25,
    "role_fit": 0.20,
    "email_confidence": 0.20,
    "phone_confidence": 0.10,
    "freshness": 0.10,
    "routability": 0.15,
}


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _dimension(value: Any, *, source: str, known: bool = True) -> dict[str, Any]:
    return {
        "score": round(_clamp(value), 1),
        "state": "known" if known else "unknown",
        "source": source,
    }


def _freshness(last_verified_at: Any, *, now: datetime) -> dict[str, Any]:
    if not isinstance(last_verified_at, datetime):
        return _dimension(0, source="missing", known=False)
    observed = last_verified_at
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    age_days = max(0, (now - observed.astimezone(timezone.utc)).days)
    if age_days <= 30:
        score = 100
    elif age_days <= 60:
        score = 75
    elif age_days <= 90:
        score = 50
    elif age_days <= 180:
        score = 25
    else:
        score = 10
    result = _dimension(score, source="last_verified_at")
    result["age_days"] = age_days
    return result


def calculate_actionable_contact_score(
    person: Any,
    *,
    role_fit_score: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Calcula score 0–100 e breakdown epistemicamente explícito.

    ``person`` pode ser model SQLAlchemy, dataclass ou mapping. O cálculo nunca
    faz I/O e não presume que um campo ausente seja um fato negativo.
    """
    current_time = now or datetime.now(timezone.utc)

    def get(name: str, default: Any = None) -> Any:
        if isinstance(person, Mapping):
            return person.get(name, default)
        return getattr(person, name, default)

    raw_data = get("raw_data") or {}
    if not isinstance(raw_data, Mapping):
        raw_data = {}

    identity_raw = get("identity_confidence")
    identity = _dimension(
        identity_raw or 0,
        source="identity_confidence" if identity_raw is not None else "missing",
        known=identity_raw is not None,
    )

    explicit_role_fit = role_fit_score
    if explicit_role_fit is None:
        explicit_role_fit = raw_data.get("role_fit_score")
    role_label = get("role_label") or raw_data.get("title") or raw_data.get("job_title")
    if explicit_role_fit is not None:
        role_fit = _dimension(explicit_role_fit, source="role_fit_score")
    elif role_label and match_persona_for_role(role_label):
        role_fit = _dimension(70, source="buyer_persona_inference")
    elif role_label:
        role_fit = _dimension(40, source="role_present_inference")
    else:
        role_fit = _dimension(0, source="missing", known=False)

    contact_confidence = get("contact_confidence")
    email = get("email")
    email_verified = bool(get("email_verified"))
    if email_verified:
        email_confidence = _dimension(100, source="email_verified")
    elif email:
        email_confidence = _dimension(
            contact_confidence or get("confidence") or 50,
            source="contact_confidence" if contact_confidence is not None else "email_present_inference",
        )
    else:
        email_confidence = _dimension(0, source="missing", known=False)

    phone = get("phone")
    if phone:
        phone_confidence = _dimension(
            contact_confidence or get("confidence") or 50,
            source="contact_confidence" if contact_confidence is not None else "phone_present_inference",
        )
    else:
        phone_confidence = _dimension(0, source="missing", known=False)

    freshness = _freshness(get("last_verified_at"), now=current_time)

    routability_type = str(get("routability_type") or "").upper()
    routability_values = {
        "DIRECT": 100,
        "DIRECT_CONTACT": 100,
        "ROUTABLE": 85,
        "ROUTABLE_CONTACT": 85,
        "INSTITUTIONAL": 50,
        "UNREACHABLE": 0,
    }
    if routability_type in routability_values:
        routability = _dimension(routability_values[routability_type], source="routability_type")
    elif bool(get("routable")):
        routability = _dimension(80, source="routable_flag")
    else:
        routability = _dimension(0, source="missing", known=False)

    breakdown = {
        "identity_confidence": identity,
        "role_fit": role_fit,
        "email_confidence": email_confidence,
        "phone_confidence": phone_confidence,
        "freshness": freshness,
        "routability": routability,
    }
    score = round(sum(breakdown[key]["score"] * weight for key, weight in _WEIGHTS.items()), 1)
    unknown_dimensions = [key for key, item in breakdown.items() if item["state"] == "unknown"]
    status = "actionable" if score >= 70 else "review" if score >= 40 else "low"
    return {
        "score": score,
        "status": status,
        "breakdown": breakdown,
        "unknown_dimensions": unknown_dimensions,
        "coverage": round((len(_WEIGHTS) - len(unknown_dimensions)) / len(_WEIGHTS), 2),
    }
