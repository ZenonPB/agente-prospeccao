"""Narrativa comercial da oportunidade (P1.10 — "Why this offer?").

Deriva do `LeadOpportunity` + `OfferProfile`, sem I/O nem persistência:
- FATOS: sinais presentes (`signals_matched`) e evidências de ICP.
- HIPÓTESE: ângulo de outreach do perfil + o que os sinais ausentes sugerem.
- VALIDAÇÃO: perguntas de qualificação do perfil + sinais ausentes a confirmar.

Sem perfil (legado/desconhecido), usa narrativa genérica — nunca quebra.
"""
from typing import Any, Dict, List, Optional


def build_opportunity_narrative(opportunity: Any, profile: Optional[Any]) -> Dict[str, List[str]]:
    """Monta a narrativa fato/hipótese/validação de uma oportunidade.

    Args:
        opportunity: `LeadOpportunity` (ou dict compatível) com score,
            signals_matched/signals_missing e evidence.
        profile: `OfferProfile` ou None (genérico).

    Returns:
        {"headline": str, "facts": [...], "hypotheses": [...],
         "validation_questions": [...]}.
    """
    if isinstance(opportunity, dict):
        offer_key = opportunity.get("offer_key", "?")
        score = opportunity.get("score", 0)
        matched = list(opportunity.get("signals_matched") or [])
        missing = list(opportunity.get("signals_missing") or [])
        evidence = list(opportunity.get("evidence") or [])
    else:
        offer_key = opportunity.offer_key
        score = opportunity.score
        matched = list(opportunity.signals_matched or [])
        missing = list(opportunity.signals_missing or [])
        evidence = list(opportunity.evidence or [])

    offer_name = offer_key
    angle = ""
    questions: List[str] = []
    if profile is not None:
        offer = getattr(profile, "offer", None) or {}
        offer_name = offer.get("name", offer_key)
        outreach = getattr(profile, "outreach", None) or {}
        angle = outreach.get("angle", "")
        qualification = getattr(profile, "qualification", None) or {}
        questions = list(qualification.get("questions") or [])

    facts = [f"Evidência observada: {sig}" for sig in matched]
    facts += [f"Evidência de ICP: {e[4:]}" for e in evidence if e.startswith("icp:")]
    if not facts:
        facts = ["Sem evidências observadas — qualificação pendente."]

    hypotheses = []
    if angle:
        hypotheses.append(f"Ângulo sugerido ({offer_name}): {angle}.")
    for sig in missing:
        hypotheses.append(f"Se {sig} se confirmar, a aderência a {offer_name} aumenta.")
    if not hypotheses:
        hypotheses = [f"Aderência a {offer_name} sustentada pelas evidências acima."]

    validation = list(questions)
    for sig in missing:
        validation.append(f"Confirmar {sig} com o contato?")
    if not validation:
        validation = ["Existe demanda ativa no momento?"]

    return {
        "headline": f"{offer_name} — {score}",
        "facts": facts,
        "hypotheses": hypotheses,
        "validation_questions": validation,
    }
