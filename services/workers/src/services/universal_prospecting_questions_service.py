"""Universal Prospecting Questions (#18) — 6 perguntas universais do agente.

Seam: ProspectingProfile → 6 perguntas formais.
Contrato único que veda agente "genuíno" — todas as camadas respondem estas 6.
"""
from typing import Any, Dict, List, Optional

_QUESTIONS = [
    "quem precisa",           # ICP: qual perfil tem a dor
    "sinais de necessidade",  # O que indica que é agora
    "capacidade de compra",   # Orçamento/porte viável
    "evento",                 # Gatilho temporal (reforma, expansão, crise)
    "decisor",                # Quem aprova a compra
    "abordagem",              # Como chegar (canal/ângulo)
]


def build_universal_questions(profile_key: str, lead_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """6 perguntas universais formalizadas — uma por camada do raciocínio."""
    return {
        "profile_key": profile_key,
        "questions": [
            {"id": i+1, "question": q, "layer": _layer_for(i)}
            for i, q in enumerate(_QUESTIONS)
        ],
        "lead_context": lead_context or {},
        "source": "universal_prospecting_questions_service",
    }


def _layer_for(idx: int) -> str:
    return ["icp", "need", "buying_power", "timing", "decision_maker", "outreach"][idx]


def validate_answer_coverage(answers: List[Optional[Any]]) -> Dict[str, Any]:
    """Valida se todas as 6 perguntas foram respondidas."""
    filled = [a for a in answers if a not in (None, "", [], {})]
    return {
        "answered": len(filled),
        "total": len(_QUESTIONS),
        "complete": len(filled) == len(_QUESTIONS),
        "coverage": round(len(filled)/len(_QUESTIONS)*100) if _QUESTIONS else 0,
    }


# --- #30 Discovery Questions: perguntas de qualificação por vertical ---
_DISCOVERY_QUESTIONS_BY_PROFILE: Dict[str, List[str]] = {
    "web_presence": [
        "Qual o objetivo principal do site? (gerar leads, vender, institucional)",
        "Quando foi a última atualização relevante no site?",
        "A empresa depende de agência ou é interno?",
    ],
    "business_opportunity": [
        "A empresa atua B2B, B2C ou ambos?",
        "Qual o ticket médio do serviço/produto principal?",
        "O processo de compra é centralizado ou descentralizado?",
    ],
    "industrial": [
        "Qual a capacidade instalada atual?",
        "A empresa terceiriza parte da produção?",
        "Existe previsão de expansão nos próximos 12 meses?",
    ],
    "generic": [
        "Qual o principal desafio da empresa hoje?",
        "Quem decide sobre novos fornecedores/parceiros?",
        "Como conheceu a AlphaMec/EJ?",
    ],
}


def discovery_questions_for(profile_key: str) -> Dict[str, Any]:
    """Perguntas de qualificação definidas pela vertical (#30)."""
    questions = _DISCOVERY_QUESTIONS_BY_PROFILE.get(profile_key, _DISCOVERY_QUESTIONS_BY_PROFILE["generic"])
    return {
        "profile_key": profile_key,
        "discovery_questions": [{"id": i+1, "question": q} for i, q in enumerate(questions)],
        "source": "universal_prospecting_questions_service.discovery_questions_for",
    }
