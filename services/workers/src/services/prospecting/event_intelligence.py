"""Inteligência determinística e genérica para eventos comerciais.

O core não conhece ofertas, verticais ou vocabulários comerciais. Regras de
contexto chegam por configuração (normalmente ``OfferProfile.discovery``), e
toda conclusão derivada permanece explicitamente ``INFERENCE``. Ausência de
evidência continua ``UNKNOWN``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _contains_any(text: str, terms: Iterable[str]) -> list[str]:
    normalized_terms = [(_norm(term), str(term)) for term in terms]
    return [original for token, original in normalized_terms if token and token in text]


def canonical_event_series_key(name: str | None, organizer: str | None, event_type: str | None = None) -> str:
    """Gera identidade estável entre edições sem depender de uma vertical."""
    def clean(value: str | None) -> str:
        text = _norm(value)
        text = re.sub(r"\b(?:19|20)\d{2}\b", " ", text)
        text = re.sub(r"\b(?:edicao|edition|ed)\s*(?:n\s*)?\d+\b", " ", text)
        text = re.sub(r"\b\d+(?:a|o)?\s+edicao\b", " ", text)
        return " ".join(text.split())

    parts = [clean(organizer), clean(name), clean(event_type)]
    return "|".join(part for part in parts if part)[:180]


@dataclass(frozen=True)
class EventContextRule:
    context_key: str
    offer_key: str
    terms: tuple[str, ...]
    demand_terms: tuple[str, ...] = ()
    segment_hint: str | None = None
    priority: int = 0
    fallback: bool = False


@dataclass(frozen=True)
class EventIntelligence:
    context: str | None
    recommended_offer_key: str | None
    segment_hint: str | None
    context_confidence: float
    evidence: list[dict[str, Any]]
    demand: dict[str, Any]
    series_key: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def context_rules_from_profiles(profiles: Iterable[Any]) -> list[EventContextRule]:
    """Extrai regras declarativas de uma coleção de OfferProfiles."""
    rules: list[EventContextRule] = []
    for profile in profiles:
        discovery = getattr(profile, "discovery", None) or {}
        raw = discovery.get("event_context") if isinstance(discovery, dict) else None
        if not isinstance(raw, Mapping):
            continue
        context_key = str(raw.get("context_key") or "").strip()
        offer_key = str(getattr(profile, "key", "") or "").strip()
        terms = tuple(str(item).strip() for item in (raw.get("terms") or []) if str(item).strip())
        if not context_key or not offer_key:
            continue
        rules.append(EventContextRule(
            context_key=context_key,
            offer_key=offer_key,
            terms=terms,
            demand_terms=tuple(str(item).strip() for item in (raw.get("demand_terms") or []) if str(item).strip()),
            segment_hint=str(raw.get("segment_hint") or "").strip() or None,
            priority=int(raw.get("priority") or 0),
            fallback=bool(raw.get("fallback")),
        ))
    return sorted(rules, key=lambda item: (item.priority, item.context_key), reverse=True)


def infer_event_intelligence(
    event: Mapping[str, Any],
    rules: Sequence[EventContextRule] = (),
    *,
    fallback_offer_key: str | None = None,
) -> EventIntelligence:
    """Classifica contexto exclusivamente pelas regras recebidas.

    A configuração define vocabulário e oferta. O core apenas compara texto,
    registra evidência e escolhe a regra de maior prioridade com match.
    """
    name = str(event.get("name") or "")
    organizer = str(event.get("organizer") or "")
    event_type = str(event.get("event_type") or "")
    description = str(event.get("description") or event.get("summary") or "")
    source_text = _norm(" ".join([name, organizer, event_type, description]))

    selected: EventContextRule | None = None
    selected_matches: list[str] = []
    fallback_rule: EventContextRule | None = None
    for rule in rules:
        if rule.fallback and fallback_rule is None:
            fallback_rule = rule
        matches = _contains_any(source_text, rule.terms)
        if matches:
            selected = rule
            selected_matches = matches
            break
    if selected is None:
        selected = fallback_rule

    evidence: list[dict[str, Any]] = []
    if selected_matches and selected is not None:
        evidence.append({
            "claim": "event_context",
            "value": selected.context_key,
            "epistemic": "INFERENCE",
            "source": "event_text",
            "evidence": sorted(set(selected_matches)),
        })

    demand_matches = _contains_any(source_text, selected.demand_terms) if selected is not None else []
    demand_known = bool(demand_matches or selected_matches)
    demand: dict[str, Any] = {
        "epistemic": "INFERENCE" if demand_known else "UNKNOWN",
        "likely": True if demand_known else None,
        "reason": "configured_context_signal" if demand_known else "insufficient_evidence",
        "evidence": sorted(set(demand_matches)),
        "estimated_min_units": None,
    }

    # Estimativa quantitativa só nasce de contagens estruturadas fornecidas pela
    # fonte. Continua INFERENCE porque categoria x colocações não prova compra.
    try:
        categories = int(event.get("category_count")) if event.get("category_count") is not None else None
        placements = int(event.get("placements_per_category")) if event.get("placements_per_category") is not None else None
    except (TypeError, ValueError):
        categories = placements = None
    if categories and placements and categories > 0 and placements > 0:
        demand.update({
            "epistemic": "INFERENCE",
            "likely": True,
            "estimated_min_units": categories * placements,
            "basis": {"category_count": categories, "placements_per_category": placements},
            "reason": "structured_categories_times_placements",
        })

    if selected_matches:
        confidence = min(0.97, 0.66 + 0.06 * len(set(selected_matches)))
    elif selected is not None and selected.fallback:
        confidence = 0.45
    else:
        confidence = 0.0

    return EventIntelligence(
        context=selected.context_key if selected is not None else None,
        recommended_offer_key=(selected.offer_key if selected is not None else fallback_offer_key),
        segment_hint=selected.segment_hint if selected is not None else None,
        context_confidence=round(confidence, 3),
        evidence=evidence,
        demand=demand,
        series_key=canonical_event_series_key(name, organizer, event_type),
    )


def score_event_timing(
    event_date: str | date | None,
    *,
    ideal_min_days: int = 21,
    ideal_max_days: int = 75,
    planning_max_days: int = 180,
) -> dict[str, Any]:
    """Calcula timing respeitando venda, aprovação e janela de execução."""
    if isinstance(event_date, date):
        target = event_date
    else:
        try:
            target = date.fromisoformat(str(event_date or "")[:10])
        except ValueError:
            target = None
    if target is None:
        return {"timing_score": 0, "urgency": "unknown", "days_until": None, "reason": "invalid_date", "purchase_window": "unknown"}

    days = (target - date.today()).days
    if days < 0:
        return {"timing_score": 0, "urgency": "expired", "days_until": days, "reason": "past_event", "purchase_window": "closed"}
    if days < 7:
        score = max(18, 42 - days * 2)
        return {"timing_score": score, "urgency": "critical", "days_until": days, "reason": "execution_window_too_short", "purchase_window": "late"}
    if days < ideal_min_days:
        score = 68 + int((days - 7) / max(1, ideal_min_days - 7) * 15)
        return {"timing_score": min(83, score), "urgency": "high", "days_until": days, "reason": "short_but_actionable", "purchase_window": "closing"}
    if days <= ideal_max_days:
        midpoint = (ideal_min_days + ideal_max_days) / 2
        spread = max(1, (ideal_max_days - ideal_min_days) / 2)
        score = int(100 - abs(days - midpoint) / spread * 12)
        return {"timing_score": max(88, score), "urgency": "high" if days <= midpoint else "medium", "days_until": days, "reason": "ideal_commercial_window", "purchase_window": "ideal"}
    if days <= planning_max_days:
        score = max(52, int(82 - (days - ideal_max_days) / max(1, planning_max_days - ideal_max_days) * 30))
        return {"timing_score": score, "urgency": "low", "days_until": days, "reason": "planning_window", "purchase_window": "planning"}
    score = max(15, 45 - int((days - planning_max_days) / 30) * 4)
    return {"timing_score": score, "urgency": "very_low", "days_until": days, "reason": "too_early_for_active_outreach", "purchase_window": "early"}
