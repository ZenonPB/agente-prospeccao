"""Learning Service (#10 Niche priors + #11 Sales outcomes).

Seam: outcomes (funil/vendas) → priors versionados por org × service × segment.
Agregação por sinal/faixa/nicho/canal — versão inicial sem ML (regras + contadores).
"""
from typing import Any, Dict, List, Optional
from collections import defaultdict

# Contadores in-memory (versão inicial; persistência em DB em evolução)
_outcome_counters: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))


def record_outcome(org_id: str, service: str, segment: str, outcome: str, channel: Optional[str] = None) -> None:
    """Registra um outcome de venda/contato para aprendizado (#11)."""
    key = f"{org_id}:{service}:{segment}"
    _outcome_counters[key][outcome] = _outcome_counters[key].get(outcome, 0) + 1
    if channel:
        _outcome_counters[key][f"channel:{channel}"] = _outcome_counters[key].get(f"channel:{channel}", 0) + 1


def compute_niche_prior(org_id: str, service: str, segment: str) -> Dict[str, Any]:
    """Calcula prior de nicho baseado em outcomes históricos (#10).

    Returns:
        {
            "org_id": str, "service": str, "segment": str,
            "total_outcomes": int, "conversion_rate": float,
            "top_channel": str, "prior_score": float (0-100),
            "source": "learning_service"
        }
    """
    key = f"{org_id}:{service}:{segment}"
    counter = _outcome_counters.get(key, {})
    total = sum(counter.get(k, 0) for k in ("WON", "MEETING", "REPLIED", "QUALIFIED", "NEW") if k in counter)
    if total == 0:
        total = sum(counter.values()) or 1

    wins = counter.get("WON", 0)
    conversion = round(wins / total * 100, 2) if total else 0.0

    # Canal com mais wins
    channel_counters = {k.replace("channel:", ""): v for k, v in counter.items() if k.startswith("channel:")}
    top_channel = max(channel_counters, key=channel_counters.get) if channel_counters else None

    # Prior score: combinação de conversão + volume
    prior_score = min(100, conversion * 0.7 + (total / 10) * 0.3)

    return {
        "org_id": org_id,
        "service": service,
        "segment": segment,
        "total_outcomes": total,
        "conversion_rate": conversion,
        "top_channel": top_channel,
        "prior_score": round(prior_score, 2),
        "source": "learning_service.compute_niche_prior",
    }


def summarize_learning(org_id: str, service: Optional[str] = None) -> Dict[str, Any]:
    """Resumo de aprendizado (#11) para dashboard."""
    results = []
    for key, counter in _outcome_counters.items():
        o, s, seg = key.split(":", 2)
        if o == org_id and (service is None or s == service):
            total = sum(counter.values())
            wins = counter.get("WON", 0)
            results.append({
                "service": s, "segment": seg,
                "total": total, "won": wins,
                "conversion_rate": round(wins / (total or 1) * 100, 2),
            })
    return {
        "org_id": org_id,
        "results": results,
        "source": "learning_service.summarize_learning",
    }


# --- #12 Precision@K ---
def precision_at_k(ranked_leads: List[Dict[str, Any]], k: int = 10, positive_outcomes: Optional[set] = None) -> Dict[str, Any]:
    """Calcula Precision@K — fração dos top-K leads que convertiram (#12).

    Args:
        ranked_leads: lista ordenada do mais ao menos provável (pipeline ranking).
        k: janela de avaliação (default 10).
        positive_outcomes: set de status considerados positivo (default: WON/MEETING).
    """
    if positive_outcomes is None:
        positive_outcomes = {"WON", "MEETING", "REPLIED"}
    window = ranked_leads[:k]
    if not window:
        return {"k": k, "precision_at_k": 0.0, "window_size": 0, "positive_count": 0, "source": "learning_service.precision_at_k"}

    positives = sum(1 for lead in window if (lead.get("outcome") or lead.get("status") or "") in positive_outcomes)
    return {
        "k": k,
        "precision_at_k": round(positives / len(window), 3),
        "window_size": len(window),
        "positive_count": positives,
        "source": "learning_service.precision_at_k",
    }


# --- #15 Golden Lead Patterns ---
_GOLDEN_PATTERNS: Dict[str, Dict[str, Any]] = {
    "web_presence_no_site": {
        "description": "Lead web sem site próprio + alta demanda local",
        "conditions": {"NO_OWN_WEBSITE": True, "GOOGLE_RATING_COUNT": ">=5"},
        "estimated_lift": 0.25,
        "evidence_required": True,
    },
    "industrial_expansion": {
        "description": "Indústria com sinal de expansão (vaga + nova filial)",
        "conditions": {"HIRING": True, "NEW_BRANCH": True},
        "estimated_lift": 0.30,
        "evidence_required": True,
    },
}


def match_golden_patterns(profile_key: str, signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Matcher de padrões compostos de golden lead (#15)."""
    matches = []
    for pattern_id, pattern in _GOLDEN_PATTERNS.items():
        # Só aplica padrões do perfil ou genéricos
        if not pattern_id.startswith(profile_key) and not pattern_id.startswith("generic"):
            continue
        conds = pattern.get("conditions", {})
        # Avaliação simples (evidência = condição verdadeira)
        met = sum(1 for k, v in conds.items() if signals.get(k) == v or (isinstance(v, bool) and v and signals.get(k)))
        if met == len(conds):
            matches.append({
                "pattern_id": pattern_id,
                "description": pattern["description"],
                "estimated_lift": pattern["estimated_lift"],
                "matched_conditions": met,
                "total_conditions": len(conds),
                "source": "learning_service.match_golden_patterns",
            })
    return matches
