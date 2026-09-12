"""Política central de freshness/TTL para dados comerciais.

Não faz I/O. Mantém a semântica de UNKNOWN separada de stale/valid e serve
API, scheduler e scoring sem duplicar regras de expiração.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any


class FreshnessState(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FreshnessPolicy:
    key: str
    ttl_days: int
    priority: int


DEFAULT_POLICIES: dict[str, FreshnessPolicy] = {
    "company_registry": FreshnessPolicy("company_registry", 60, 70),
    "website": FreshnessPolicy("website", 30, 65),
    "technographics": FreshnessPolicy("technographics", 30, 75),
    "employment": FreshnessPolicy("employment", 30, 90),
    "email": FreshnessPolicy("email", 30, 95),
    "phone": FreshnessPolicy("phone", 60, 85),
    "jobs": FreshnessPolicy("jobs", 14, 80),
    "news": FreshnessPolicy("news", 14, 70),
    "social": FreshnessPolicy("social", 14, 55),
    "intent": FreshnessPolicy("intent", 14, 90),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_observed_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def evaluate_freshness(
    key: str,
    observed_at: Any,
    *,
    now: datetime | None = None,
    expires_at: Any = None,
) -> dict[str, Any]:
    """Retorna estado explicável sem converter ausência em informação velha."""
    current = now or utc_now()
    observed = parse_observed_at(observed_at)
    explicit_expiry = parse_observed_at(expires_at)
    policy = DEFAULT_POLICIES.get(key, FreshnessPolicy(key, 30, 50))

    if observed is None and explicit_expiry is None:
        return {
            "key": key,
            "state": FreshnessState.UNKNOWN.value,
            "observed_at": None,
            "expires_at": None,
            "age_days": None,
            "ttl_days": policy.ttl_days,
            "priority": policy.priority,
        }

    if explicit_expiry is None and observed is not None:
        explicit_expiry = observed + timedelta(days=policy.ttl_days)

    stale = bool(explicit_expiry and current >= explicit_expiry)
    age_days = None
    if observed is not None:
        age_days = max(0, int((current - observed).total_seconds() // 86400))

    return {
        "key": key,
        "state": FreshnessState.STALE.value if stale else FreshnessState.FRESH.value,
        "observed_at": observed.isoformat() if observed else None,
        "expires_at": explicit_expiry.isoformat() if explicit_expiry else None,
        "age_days": age_days,
        "ttl_days": policy.ttl_days,
        "priority": policy.priority,
    }


def event_freshness(event_date: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Eventos expiram na própria data; datas ausentes continuam UNKNOWN."""
    current = now or utc_now()
    if event_date is None:
        return evaluate_freshness("event", None, now=current)
    if isinstance(event_date, datetime):
        expiry = event_date
    else:
        try:
            expiry = datetime.combine(event_date, datetime.max.time(), tzinfo=timezone.utc)
        except TypeError:
            return evaluate_freshness("event", None, now=current)
    return evaluate_freshness("event", current, now=current, expires_at=expiry)
