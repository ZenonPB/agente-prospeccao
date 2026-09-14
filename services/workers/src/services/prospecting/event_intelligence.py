"""Inteligência determinística para eventos comerciais.

O módulo não consulta rede nem transforma ausência de informação em fato. Ele
classifica contexto a partir do texto/evidências já coletados, recomenda a
oferta apropriada e calcula timing respeitando a janela comercial da oferta.

Toda conclusão derivada é explicitamente marcada como INFERENCE. Campos que a
fonte trouxe de forma estruturada podem sustentar uma inferência quantitativa,
mas nunca são promovidos para FACT por este módulo.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
import re
import unicodedata
from typing import Any, Iterable


MEJ_TERMS = (
    "movimento empresa junior", "movimento empresa júnior", "empresa junior",
    "empresa júnior", "empresas juniores", "federacao de empresas juniores",
    "federação de empresas juniores", "nucleo de empresas juniores",
    "núcleo de empresas juniores", "brasil junior", "brasil júnior",
    "enej", "esej", "interej", "sudenej", "mej",
)
SPORTS_TERMS = (
    "campeonato", "corrida", "copa", "torneio", "liga", "olimpiada",
    "olimpíada", "competicao", "competição", "maratona", "circuito",
    "festival esportivo", "jogos universitarios", "jogos universitários",
    "federacao", "federação", "confederacao", "confederação",
)
AWARD_TERMS = (
    "premiacao", "premiação", "premio", "prêmio", "trofeu", "troféu",
    "medalha", "podio", "pódio", "reconhecimento", "award", "ranking",
    "campeao", "campeão", "categoria", "colocacao", "colocação",
)


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def _contains_any(text: str, terms: Iterable[str]) -> list[str]:
    normalized_terms = [(_norm(term), term) for term in terms]
    return [original for token, original in normalized_terms if token and token in text]


def canonical_event_series_key(name: str | None, organizer: str | None, event_type: str | None = None) -> str:
    """Identidade estável entre edições do mesmo evento.

    Remove ano e marcadores usuais de edição, mas mantém organizador e família
    para reduzir colisões entre eventos homônimos.
    """
    def clean(value: str | None) -> str:
        text = _norm(value)
        text = re.sub(r"\b(?:19|20)\d{2}\b", " ", text)
        text = re.sub(r"\b(?:edicao|edition|ed)\s*(?:n\s*)?\d+\b", " ", text)
        text = re.sub(r"\b\d+(?:a|o)?\s+edicao\b", " ", text)
        return " ".join(text.split())

    parts = [clean(organizer), clean(name), clean(event_type)]
    key = "|".join(part for part in parts if part)
    return key[:180]


@dataclass(frozen=True)
class EventIntelligence:
    context: str
    recommended_offer_key: str
    context_confidence: float
    evidence: list[dict[str, Any]]
    award_demand: dict[str, Any]
    series_key: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def infer_event_intelligence(event: dict[str, Any]) -> EventIntelligence:
    """Classifica o evento usando apenas evidências presentes no payload."""
    name = str(event.get("name") or "")
    organizer = str(event.get("organizer") or "")
    event_type = str(event.get("event_type") or "")
    description = str(event.get("description") or event.get("summary") or "")
    source_text = _norm(" ".join([name, organizer, event_type, description]))

    mej_matches = _contains_any(source_text, MEJ_TERMS)
    sports_matches = _contains_any(source_text, SPORTS_TERMS)
    award_matches = _contains_any(source_text, AWARD_TERMS)

    evidence: list[dict[str, Any]] = []
    if mej_matches:
        evidence.append({
            "claim": "context_mej",
            "epistemic": "INFERENCE",
            "source": "event_text",
            "evidence": sorted(set(mej_matches)),
        })
    if sports_matches:
        evidence.append({
            "claim": "context_sports",
            "epistemic": "INFERENCE",
            "source": "event_text",
            "evidence": sorted(set(sports_matches)),
        })
    if award_matches:
        evidence.append({
            "claim": "award_demand_signal",
            "epistemic": "INFERENCE",
            "source": "event_text",
            "evidence": sorted(set(award_matches)),
        })

    if mej_matches:
        context = "mej"
        offer_key = "trophies_mej"
        confidence = min(0.96, 0.7 + 0.06 * len(set(mej_matches)))
    elif sports_matches:
        context = "sports"
        offer_key = "trophies_sports"
        confidence = min(0.94, 0.66 + 0.05 * len(set(sports_matches)))
    else:
        context = "general"
        offer_key = "trophies"
        confidence = 0.5

    award_demand: dict[str, Any] = {
        "epistemic": "INFERENCE" if award_matches or sports_matches or mej_matches else "UNKNOWN",
        "likely": bool(award_matches or sports_matches or mej_matches) if (award_matches or sports_matches or mej_matches) else None,
        "reason": "explicit_or_contextual_award_signal" if (award_matches or sports_matches or mej_matches) else "insufficient_evidence",
        "estimated_min_units": None,
    }

    # Quantidade estimada só existe se a fonte trouxe contagens estruturadas.
    # Mesmo assim continua INFERENCE: categoria x colocações não prova pedido.
    try:
        categories = int(event.get("category_count")) if event.get("category_count") is not None else None
        placements = int(event.get("placements_per_category")) if event.get("placements_per_category") is not None else None
    except (TypeError, ValueError):
        categories = placements = None
    if categories and placements and categories > 0 and placements > 0:
        award_demand.update({
            "epistemic": "INFERENCE",
            "likely": True,
            "estimated_min_units": categories * placements,
            "basis": {"category_count": categories, "placements_per_category": placements},
            "reason": "structured_categories_times_placements",
        })

    return EventIntelligence(
        context=context,
        recommended_offer_key=offer_key,
        context_confidence=round(confidence, 3),
        evidence=evidence,
        award_demand=award_demand,
        series_key=canonical_event_series_key(name, organizer, event_type),
    )


def score_event_timing(
    event_date: str | date | None,
    *,
    ideal_min_days: int = 21,
    ideal_max_days: int = 75,
    planning_max_days: int = 180,
) -> dict[str, Any]:
    """Timing comercial orientado a produção + ciclo de venda.

    Eventos imediatos não recebem nota máxima: para produtos personalizados,
    proximidade excessiva reduz a viabilidade de contato, aprovação e produção.
    """
    if isinstance(event_date, date):
        target = event_date
    else:
        try:
            target = date.fromisoformat(str(event_date or "")[:10])
        except ValueError:
            target = None
    if target is None:
        return {
            "timing_score": 0,
            "urgency": "unknown",
            "days_until": None,
            "reason": "invalid_date",
            "purchase_window": "unknown",
        }

    days = (target - date.today()).days
    if days < 0:
        return {"timing_score": 0, "urgency": "expired", "days_until": days, "reason": "past_event", "purchase_window": "closed"}
    if days < 7:
        score = max(18, 42 - days * 2)
        return {"timing_score": score, "urgency": "critical", "days_until": days, "reason": "production_window_too_short", "purchase_window": "late"}
    if days < ideal_min_days:
        score = 68 + int((days - 7) / max(1, ideal_min_days - 7) * 15)
        return {"timing_score": min(83, score), "urgency": "high", "days_until": days, "reason": "short_but_actionable", "purchase_window": "closing"}
    if days <= ideal_max_days:
        midpoint = (ideal_min_days + ideal_max_days) / 2
        spread = max(1, (ideal_max_days - ideal_min_days) / 2)
        score = int(100 - abs(days - midpoint) / spread * 12)
        return {"timing_score": max(88, score), "urgency": "high" if days <= midpoint else "medium", "days_until": days, "reason": "ideal_sales_and_production_window", "purchase_window": "ideal"}
    if days <= planning_max_days:
        score = max(52, int(82 - (days - ideal_max_days) / max(1, planning_max_days - ideal_max_days) * 30))
        return {"timing_score": score, "urgency": "low", "days_until": days, "reason": "planning_window", "purchase_window": "planning"}
    score = max(15, 45 - int((days - planning_max_days) / 30) * 4)
    return {"timing_score": score, "urgency": "very_low", "days_until": days, "reason": "too_early_for_active_outreach", "purchase_window": "early"}
