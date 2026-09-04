"""Archetypes as Fallback (#32) — perfis pré-moldados quando o template não cobre.

Seam: campaign context + missing template → archetype (inferred profile).
Evita fallback silencioso para 'generic' — usa templates conhecidos como
referência.
"""
from typing import Any, Dict, Optional

# Archetypes: conjunto de perfis de campanha conhecidos.
# Se nenhum template se aplica, derivamos o melhor archetype por keywords do serviço.
ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "landing_pages": {
        "profile_key": "web_presence",
        "prescoring_config": {
            "enabled": True, "threshold": 50, "top_k": 30,
            "weights": {"NO_OWN_WEBSITE": 25, "HAS_INSTAGRAM": 12, "HAS_PHONE": 8, "GOOGLE_RATING": 15, "GOOGLE_RATING_COUNT": 15},
        },
        "signals_keywords": ["landing page", "página de captura", "site institucional"],
    },
    "industrial_erp": {
        "profile_key": "industrial",
        "prescoring_config": {
            "enabled": True, "threshold": 40, "top_k": 20,
            "weights": {"HAS_PHONE": 8, "GOOGLE_RATING": 8, "GOOGLE_RATING_COUNT": 8},
        },
        "signals_keywords": ["erp industrial", "metalúrgica", "manufatura", "cnc"],
    },
    "b2b_software": {
        "profile_key": "business_opportunity",
        "prescoring_config": {
            "enabled": True, "threshold": 45, "top_k": 25,
            "weights": {"HAS_OWN_WEBSITE": 10, "HAS_PHONE": 10, "GOOGLE_RATING": 10, "GOOGLE_RATING_COUNT": 10},
        },
        "signals_keywords": ["b2b", "software corporativo", "sistema web", "aplicação web"],
    },
}


def match_archetype(target_service: str, target_segment: Optional[str] = None) -> Dict[str, Any]:
    """Detecta archetype por keywords do serviço/segmento (#32).

    Returns:
        {"archetype_id": str|None, "profile_key": str, "config": dict, "confidence": float}
    """
    if not target_service:
        return {"archetype_id": None, "profile_key": "generic", "config": {}, "confidence": 0.0}

    text = f"{target_service} {target_segment or ''}".lower()
    best_id, best_score = None, 0
    for arch_id, arch in ARCHETYPES.items():
        score = sum(1 for kw in arch["signals_keywords"] if kw in text)
        if score > best_score:
            best_id, best_score = arch_id, score
    if best_id is None:
        return {"archetype_id": None, "profile_key": "generic", "config": {}, "confidence": 0.0}
    arch = ARCHETYPES[best_id]
    return {
        "archetype_id": best_id,
        "profile_key": arch["profile_key"],
        "config": arch["prescoring_config"],
        "confidence": min(0.95, 0.4 + best_score * 0.2),
    }
