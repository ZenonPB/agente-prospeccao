"""Compilação de feedbacks de score em regras de calibração (Fase 2).

O consultor discorda do score da IA (ScoringFeedback). Acumulados por
template × organização, esses feedbacks são resumidos pela LLM em 3–6 regras
objetivas ("sites amadores pesam MAIS em campanhas de redesign"), guardadas
em TemplateLearning e injetadas no prompt de scoring como contexto — nunca
como comando determinístico. Ver docs/ai-feedback-loop.md.
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.models import FeedbackStatus, ScoringFeedback, TemplateLearning
from services.provider_client import groq_json_chat
from config.settings import settings

logger = logging.getLogger(__name__)

# Mesma URL usada pelos demais serviços Groq (scoring_service, template_router).
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

MAX_RULES = 10

_SYSTEM_PROMPT = (
    "Você é um analista que converte correções humanas de score em regras de "
    "calibração para uma IA de prospecção B2B. Recebe feedbacks (score da IA, "
    "score do consultor, motivo em texto livre) e resume PADRÕES recorrentes em "
    "regras objetivas, curtas e acionáveis em pt-BR (ex.: 'sites atualizados e "
    "bem apresentados pesam MENOS em campanhas de redesign'). "
    "Só crie regra quando houver padrão (pelo menos 2 feedbacks na mesma "
    "direção) ou um motivo muito bem justificado. "
    "Nunca invente critérios que não estejam nos feedbacks. "
    "Responda SOMENTE com JSON: {\"rules\": [\"...\"]} (3 a 6 regras)."
)

_COMPACT_SYSTEM_PROMPT = (
    "Você mantém uma lista de regras de calibração de scoring já existentes e "
    "recebe novas regras. Compacte tudo em no máximo "
    f"{MAX_RULES} regras objetivas, curtas, em pt-BR, sem duplicatas e mesclando "
    "regras redundantes. Preserve o sentido de cada regra. "
    "Responda SOMENTE com JSON: {\"rules\": [\"...\"]}."
)


def _feedback_line(fb: ScoringFeedback) -> str:
    direction = "IA pontuou de MENOS" if fb.direction.value == "MUITO_BAIXO" else "IA pontuou DEMAIS"
    return (
        f"- IA: {fb.original_score} | consultor: {fb.suggested_score} "
        f"({direction}) | motivo: {fb.reason or '(não informado)'}"
    )


async def _llm_rules(system_prompt: str, user_prompt: str, db: Session, organization_id: Any) -> Optional[List[str]]:
    data = await groq_json_chat(
        api_key=settings.GROQ_API_KEY,
        model=settings.GROQ_MODEL_CLASSIFY,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        url=GROQ_URL,
        max_tokens=1024,
        temperature=0.1,
        db=db,
        organization_id=organization_id,
    )
    if not data:
        return None
    rules = data.get("rules")
    if not isinstance(rules, list):
        return None
    return [str(r).strip() for r in rules if str(r).strip()]


def get_learning_rules(db: Session, organization_id: Any, template_id: Any) -> List[str]:
    """Regras de calibração ativas para o template × organização."""
    if not organization_id or not template_id:
        return []
    row = (
        db.query(TemplateLearning)
        .filter(
            TemplateLearning.organization_id == organization_id,
            TemplateLearning.template_id == template_id,
        )
        .first()
    )
    return list(row.instructions or []) if row else []


async def compile_learnings(
    db: Session,
    organization_id: Any,
    template_id: Any,
) -> Optional[Dict[str, Any]]:
    """Compila feedbacks pendentes do template em regras (upsert TemplateLearning).

    Retorna dict com `compiled` (feedbacks consumidos), `rules` (lista final) e
    `compacted` (se houve compactação). `None` em falha de LLM ou sem insumo.
    """
    if not template_id:
        return None

    feedbacks = (
        db.query(ScoringFeedback)
        .filter(
            ScoringFeedback.organization_id == organization_id,
            ScoringFeedback.template_id == template_id,
            ScoringFeedback.status.in_([FeedbackStatus.PENDING, FeedbackStatus.APPLIED]),
        )
        .order_by(ScoringFeedback.created_at)
        .limit(100)
        .all()
    )
    if not feedbacks:
        return None

    user_prompt = (
        "Feedbacks de score do time de vendas sobre a IA:\n"
        + "\n".join(_feedback_line(fb) for fb in feedbacks)
        + "\n\nResuma os padrões em 3 a 6 regras de calibração."
    )
    new_rules = await _llm_rules(_SYSTEM_PROMPT, user_prompt, db, organization_id)
    if not new_rules:
        logger.warning(
            "Compilação de aprendizados falhou (LLM) — feedbacks permanecem pendentes."
        )
        return None

    learning = (
        db.query(TemplateLearning)
        .filter(
            TemplateLearning.organization_id == organization_id,
            TemplateLearning.template_id == template_id,
        )
        .first()
    )
    existing: List[str] = list(learning.instructions or []) if learning else []
    combined = existing + new_rules

    compacted = False
    if len(combined) > MAX_RULES:
        compact_prompt = (
            "Regras existentes:\n" + "\n".join(f"- {r}" for r in combined)
            + f"\n\nCompacte em no máximo {MAX_RULES} regras, mesclando redundâncias."
        )
        merged = await _llm_rules(_COMPACT_SYSTEM_PROMPT, compact_prompt, db, organization_id)
        if merged:
            combined = merged
            compacted = True
        else:
            # Sem LLM para compactar: mantém as mais recentes dentro do cap.
            combined = combined[-MAX_RULES:]

    if learning is None:
        learning = TemplateLearning(
            organization_id=organization_id,
            template_id=template_id,
        )
        db.add(learning)
    learning.instructions = combined
    learning.compiled_from = (learning.compiled_from or 0) + len(feedbacks)

    for fb in feedbacks:
        fb.status = FeedbackStatus.COMPILED

    db.commit()
    logger.info(
        "Aprendizado compilado: template=%s org=%s feedbacks=%d regras=%d compacted=%s",
        template_id, organization_id, len(feedbacks), len(combined), compacted,
    )
    return {
        "compiled": len(feedbacks),
        "rules": combined,
        "compacted": compacted,
    }
