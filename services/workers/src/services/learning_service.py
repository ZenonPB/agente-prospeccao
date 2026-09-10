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
        # Sem outcomes relevantes: NÃO invente denominador 1 (consolidação §27:
        # "Não esconder UNKNOWN") — retorna total=0 e conversion=0
        total = 0

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


# --- #15 Golden Lead Patterns (P1.28: associados a OfferProfile) ---
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
    # P1.28 — patterns por oferta (condições = sinais booleanos observados).
    "landing_page_no_site_social": {
        "description": "Sem site próprio + Instagram ativo: público-alvo de landing page",
        "profiles": ["landing_page"],
        "conditions": {"NO_OWN_WEBSITE": True, "HAS_INSTAGRAM": True},
        "estimated_lift": 0.35,
        "evidence_required": True,
    },
    "mechanical_project_formalizada": {
        "description": "Indústria formalizada (CNPJ + e-mail corporativo): base para projeto mecânico",
        "profiles": ["mechanical_project"],
        "conditions": {"HAS_CNPJ": True, "HAS_BUSINESS_EMAIL": True},
        "estimated_lift": 0.25,
        "evidence_required": True,
    },
    "technical_drawing_contato_direto": {
        "description": "Contato direto (telefone + e-mail corporativo): desenho técnico vende para quem atende",
        "profiles": ["technical_drawing"],
        "archetypes": ["industrial"],
        "conditions": {"HAS_PHONE": True, "HAS_BUSINESS_EMAIL": True},
        "estimated_lift": 0.25,
        "evidence_required": True,
    },
    "machine_manual_fabricante_contatavel": {
        "description": "Fabricante formalizado e contatável: base para manual/NR-12",
        "profiles": ["machine_manual"],
        "archetypes": ["industrial"],
        "conditions": {"HAS_CNPJ": True, "HAS_PHONE": True},
        "estimated_lift": 0.25,
        "evidence_required": True,
    },
    "trophies_evento_ativo": {
        "description": "Promove eventos + Instagram ativo: janela aberta para troféus",
        "profiles": ["trophies"],
        "conditions": {"HOSTS_EVENTS": True, "HAS_INSTAGRAM": True},
        "estimated_lift": 0.40,
        "evidence_required": True,
    },
}


def match_golden_patterns(profile_key: str, signals: Dict[str, Any],
                           archetype: Optional[str] = None) -> List[Dict[str, Any]]:
    """Matcher de padrões compostos de golden lead (#15, P1.28).

    Um padrão aplica-se quando casa com a oferta (`profiles`), com o
    arquétipo (`archetypes`), pelo prefixo legado (`<profile_key>_...`) ou
    por prefixo `generic_`. Todas as condições precisam ser atendidas —
    padrão parcial nunca é reportado como match.
    """
    matches = []
    for pattern_id, pattern in _GOLDEN_PATTERNS.items():
        profiles = pattern.get("profiles") or []
        archetypes = pattern.get("archetypes") or []
        scoped = bool(profiles or archetypes)
        applies = (
            profile_key in profiles
            or (archetype is not None and archetype in archetypes)
            or (not scoped and (pattern_id.startswith(profile_key)
                                or pattern_id.startswith("generic")))
        )
        if not applies:
            continue
        conds = pattern.get("conditions", {})
        # Avaliação simples (evidência = condição verdadeira)
        met = sum(
            1
            for k, expected in conds.items()
            if (
                signals.get(k) is expected
                if isinstance(expected, bool)
                else signals.get(k) == expected
            )
        )
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


# --- #33 Three-Level Learning ---
class ThreeLevelLearning:
    """Aprendizado em 3 níveis com precedência explícita: GLOBAL → VERTICAL → ORGANIZATION.

    Versão inicial sem ML — contadores por nível + resolução de conflito.
    Por organização, mantém consistência da regra de aprendizado.
    """

    def __init__(self):
        self._global: Dict[str, Any] = {}
        self._vertical: Dict[str, Dict[str, Any]] = {}
        self._org: Dict[str, Dict[str, Any]] = {}

    def set_global(self, key: str, value: Any) -> None:
        self._global[key] = value

    def set_vertical(self, vertical: str, key: str, value: Any) -> None:
        self._vertical.setdefault(vertical, {})[key] = value

    def set_org(self, org_id: str, key: str, value: Any) -> None:
        self._org.setdefault(org_id, {})[key] = value

    def resolve(self, key: str, vertical: Optional[str] = None, org_id: Optional[str] = None) -> Dict[str, Any]:
        """Resolve precedência: org > vertical > global."""
        value = None
        source = "default"
        if org_id and org_id in self._org and key in self._org[org_id]:
            value, source = self._org[org_id][key], "ORGANIZATION"
        elif vertical and vertical in self._vertical and key in self._vertical[vertical]:
            value, source = self._vertical[vertical][key], "VERTICAL"
        elif key in self._global:
            value, source = self._global[key], "GLOBAL"
        return {"key": key, "value": value, "source": source, "key_as_str": str(key)}


three_level_learning = ThreeLevelLearning()
