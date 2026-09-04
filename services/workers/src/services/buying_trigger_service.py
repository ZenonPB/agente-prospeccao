"""Buying Trigger (#26) + ICP vs Intent (#19) — detecção de gatilho de compra.

Seam: IntentEngine events → BuyingTrigger (gatilho acionável).
Distingue ICP (perfil fixo) de Intent (evento transitório).
"""
from typing import Any, Dict, List, Optional
from services.intent_engine_service import IntentEngine
from services.prospecting_profile_service import (
    PROFILE_WEB_PRESENCE, PROFILE_BUSINESS, PROFILE_INDUSTRIAL,
)

# ICP por perfil (perfil fixo de cliente ideal — não muda com eventos)
ICP_BY_PROFILE: Dict[str, Dict[str, Any]] = {
    PROFILE_WEB_PRESENCE: {"size": "micro_pequena", "segment": "varejo/lojas", "has_site": "weak_or_none"},
    PROFILE_BUSINESS:     {"size": "media_grande", "segment": "industria/servicos", "has_site": "any"},
    PROFILE_INDUSTRIAL:   {"size": "media_grande", "segment": "industria_manufactura", "has_site": "any"},
}

# Mapa: evento de intenção → gatilho acionável (texto de lead para SDR)
TRIGGER_MAP: Dict[str, str] = {
    "HIRING":         "Expansão de equipe - abertura de vagas",
    "NEW_BRANCH":     "Abertura de nova filial/unidade",
    "NEW_EQUIPMENT":  "Investimento em novo equipamento/produto",
    "EXPANDING":      "Sinal de expansão de mercado",
    "NEW_PRODUCT":    "Lançamento de novo produto/serviço",
}

_engine = IntentEngine()


def classify_intent(profile_key: str, icp_match: bool, intent_score: float) -> str:
    """Classifica a intenção: PROFILED (ICP fixo) vs TIMELY (evento recente)."""
    if intent_score >= 60:
        return "TIMELY"
    return "PROFILED" if icp_match else "COLD"


def detect_buying_triggers(events: List[Dict]) -> List[Dict[str, Any]]:
    """Gera gatilhos acionáveis a partir de eventos de intenção (Fase 3 — #26)."""
    triggers = []
    for e in events:
        key = e.get("key")
        if key in TRIGGER_MAP:
            triggers.append({
                "trigger": key,
                "label": TRIGGER_MAP[key],
                "confidence": e.get("confidence", 0.7),
                "observed_at": e.get("observed_at"),
                "evidence_ref": e.get("evidence_refs", [e.get("evidence")]),
                "source": "buying_trigger_service",
            })
    return triggers


def icp_vs_intent(profile_key: str, intent_score: float, icp_match: bool) -> Dict[str, Any]:
    """Resolve a distinção ICP (fixo) vs Intent (evento) para o lead (#19)."""
    icp = ICP_BY_PROFILE.get(profile_key, ICP_BY_PROFILE.get(PROFILE_WEB_PRESENCE))
    classification = classify_intent(profile_key, icp_match, intent_score)
    return {
        "profile_key": profile_key,
        "icp": icp,
        "icp_match": icp_match,
        "intent_score": intent_score,
        "classification": classification,
        "frame": "intent" if classification == "TIMELY" else ("icp" if icp_match else "cold"),
        "source": "buying_trigger_service.icp_vs_intent",
    }
