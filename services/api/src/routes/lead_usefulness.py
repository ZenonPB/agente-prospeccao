"""Feedback simples de utilidade do lead — 👍 útil / 👎 não útil.

Complementa o score-feedback (que calibra o número): aqui o vendedor diz se
o lead serve, com motivo fechado quando não serve. Org-scoped, idempotente
por (lead, usuário) e auditável na trilha do lead.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.dependencies import get_db
from src.db.models import (
    Lead,
    LeadActivity,
    LeadActivityAction,
    LeadActivityAction as _ActivityCheck,
    LeadUsefulnessFeedback,
    LeadUsefulnessReason,
    Organization,
    User,
)
from src.auth.dependencies import get_current_user, get_user_organization

router = APIRouter(prefix="/leads", tags=["lead-usefulness"])
logger = logging.getLogger(__name__)

_REASONS = {item.value for item in LeadUsefulnessReason}

# Novo valor de trilha ainda pode não existir no enum do banco (migration
# pendente de upgrade): usa SCORE_FEEDBACK como fallback auditável.
try:
    _FEEDBACK_ACTION = LeadActivityAction.LEAD_FEEDBACK
except AttributeError:  # pragma: no cover - compatibilidade transitória
    _FEEDBACK_ACTION = LeadActivityAction.SCORE_FEEDBACK
_LEGACY_CHECK = getattr(_ActivityCheck, "LEAD_FEEDBACK", None)


class UsefulnessFeedbackRequest(BaseModel):
    useful: bool = Field(..., description="True = útil (👍); False = não útil (👎).")
    reason: Optional[str] = Field(
        None, description="Motivo fechado quando useful=False.",
    )
    detail: Optional[str] = Field(None, max_length=2000)


class UsefulnessFeedbackResponse(BaseModel):
    id: str
    lead_id: str
    useful: bool
    reason: Optional[str] = None
    updated: bool = False


def _coerce_reason(reason: Optional[str]) -> Optional[LeadUsefulnessReason]:
    """Valida o motivo contra a taxonomia fechada."""
    if reason is None:
        return None
    normalized = str(reason).strip().upper()
    try:
        return LeadUsefulnessReason(normalized)
    except ValueError:
        raise HTTPException(status_code=422, detail="Motivo inválido") from None


@router.post("/{lead_id}/usefulness-feedback", response_model=UsefulnessFeedbackResponse)
def create_usefulness_feedback(
    lead_id: str,
    body: UsefulnessFeedbackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
):
    """Registra 👍/👎 do vendedor sobre o lead (idempotente por usuário)."""
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == org.id,
    ).first()
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    if not body.useful and not body.reason:
        raise HTTPException(status_code=422, detail="Informe o motivo")
    reason = _coerce_reason(body.reason)
    if not body.useful and reason is None:
        raise HTTPException(status_code=422, detail="Informe o motivo")

    existing = db.query(LeadUsefulnessFeedback).filter(
        LeadUsefulnessFeedback.lead_id == lead.id,
        LeadUsefulnessFeedback.user_id == user.id,
    ).first()

    if existing is not None:
        existing.useful = body.useful
        existing.reason = reason
        existing.detail = body.detail
        db.add(existing)
        db.add(LeadActivity(
            lead_id=lead.id,
            user_id=user.id,
            action=_FEEDBACK_ACTION,
            detail=(
                f"Feedback atualizado: {'útil' if body.useful else 'não útil'}"
                + (f" — motivo: {reason.value}" if reason else "")
            ),
        ))
        db.commit()
        return UsefulnessFeedbackResponse(
            id=str(existing.id),
            lead_id=str(lead.id),
            useful=bool(existing.useful),
            reason=reason.value if reason else None,
            updated=True,
        )

    feedback = LeadUsefulnessFeedback(
        organization_id=org.id,
        lead_id=lead.id,
        user_id=user.id,
        campaign_id=lead.campaign_id,
        useful=body.useful,
        reason=reason,
        detail=body.detail,
    )
    db.add(feedback)
    db.add(LeadActivity(
        lead_id=lead.id,
        user_id=user.id,
        action=_FEEDBACK_ACTION,
        detail=(
            f"Feedback: {'útil' if body.useful else 'não útil'}"
            + (f" — motivo: {reason.value}" if reason else "")
        ),
    ))
    db.commit()
    logger.info("Feedback de utilidade registrado lead=%s useful=%s", lead.id, body.useful)

    return UsefulnessFeedbackResponse(
        id=str(feedback.id),
        lead_id=str(lead.id),
        useful=body.useful,
        reason=reason.value if reason else None,
        updated=False,
    )
