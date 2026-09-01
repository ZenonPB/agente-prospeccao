"""Feedback humano sobre o score da IA — insumo do loop de aprendizado.

O consultor discorda do score de um lead (score sugerido + motivo). O
feedback fica registrado (auditável na trilha do lead) e, acumulado por
template/organização, será compilado em regras de calibração injetadas no
prompt de scoring — ver docs/ai-feedback-loop.md.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.db.dependencies import get_db
from src.db.models import (
    FeedbackDirection,
    FeedbackStatus,
    Lead,
    LeadActivity,
    LeadActivityAction,
    LeadStatus,
    ScoringFeedback,
    User,
    Organization,
)
from src.auth.dependencies import get_current_user, get_user_organization

router = APIRouter(prefix="/leads", tags=["score-feedback"])
logger = logging.getLogger(__name__)

# Status do funil em que a correção manual de score pode reclassificar o lead
# (QUALIFICADO/DESQUALIFICADO). Depois de CONTATADO, o score é histórico —
# não reclassificamos (business-rules).
_RECLASSIFIABLE = (
    LeadStatus.NOVO, LeadStatus.ANALISADO,
    LeadStatus.QUALIFICADO, LeadStatus.DESQUALIFICADO,
)


class ScoreFeedbackRequest(BaseModel):
    suggested_score: int = Field(..., ge=0, le=100)
    reason: str = Field(..., min_length=5, max_length=2000)
    apply_to_lead: bool = Field(
        True,
        description="Se true, corrige o score do lead imediatamente (auditable).",
    )


class ScoreFeedbackResponse(BaseModel):
    id: str
    lead_id: str
    original_score: int
    suggested_score: int
    direction: str
    status: str
    applied_to_lead: bool
    lead_status: Optional[str] = None


def _direction(original: int, suggested: int) -> FeedbackDirection:
    return FeedbackDirection.MUITO_ALTO if suggested < original else FeedbackDirection.MUITO_BAIXO


@router.post("/{lead_id}/score-feedback", response_model=ScoreFeedbackResponse)
def create_score_feedback(
    lead_id: str,
    body: ScoreFeedbackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
):
    """Registra discordância com o score da IA e, opcionalmente, corrige o lead."""
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == org.id,
    ).first()
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if lead.qualification_score is None:
        raise HTTPException(status_code=409, detail="Lead ainda não possui score da IA")

    original = int(lead.qualification_score)
    suggested = int(body.suggested_score)
    if suggested == original:
        raise HTTPException(status_code=422, detail="Score sugerido igual ao score atual")

    applied = False
    if body.apply_to_lead:
        lead.qualification_score = suggested
        applied = True
        # Regra de negócio: >= 60 → QUALIFICADO, senão DESQUALIFICADO. Só
        # reclassifica no topo do funil (depois de CONTATADO é histórico).
        if lead.status in _RECLASSIFIABLE:
            target = LeadStatus.QUALIFICADO if suggested >= 60 else LeadStatus.DESQUALIFICADO
            if lead.status != target:
                lead.status = target
        db.add(LeadActivity(
            lead_id=lead.id,
            user_id=user.id,
            action=LeadActivityAction.SCORE_FEEDBACK,
            detail=(
                f"Score corrigido {original} → {suggested} por feedback do "
                f"consultor. Motivo: {body.reason}"
            ),
        ))

    feedback = ScoringFeedback(
        organization_id=org.id,
        lead_id=lead.id,
        user_id=user.id,
        campaign_id=lead.campaign_id,
        template_id=lead.campaign.scoring_template_id if lead.campaign else None,
        original_score=original,
        suggested_score=suggested,
        direction=_direction(original, suggested),
        reason=body.reason,
        status=FeedbackStatus.APPLIED if applied else FeedbackStatus.PENDING,
        applied_at=datetime.now(timezone.utc) if applied else None,
    )
    db.add(feedback)
    db.commit()

    return ScoreFeedbackResponse(
        id=str(feedback.id),
        lead_id=str(lead.id),
        original_score=original,
        suggested_score=suggested,
        direction=feedback.direction.value,
        status=feedback.status.value,
        applied_to_lead=applied,
        lead_status=lead.status.value if lead.status else None,
    )


class ScoreFeedbackItem(BaseModel):
    id: str
    lead_id: str
    company_name: Optional[str] = None
    campaign_id: Optional[str] = None
    original_score: int
    suggested_score: int
    direction: str
    reason: Optional[str] = None
    status: str
    created_at: str


@router.get("/score-feedback", response_model=list[ScoreFeedbackItem])
def list_score_feedbacks(
    campaign_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
):
    """Lista feedbacks de score da organização (para revisão/compilação)."""
    query = db.query(ScoringFeedback).filter(
        ScoringFeedback.organization_id == org.id,
    )
    if campaign_id:
        query = query.filter(ScoringFeedback.campaign_id == campaign_id)
    if status:
        try:
            query = query.filter(ScoringFeedback.status == FeedbackStatus(status))
        except ValueError:
            raise HTTPException(status_code=422, detail="Status inválido")

    items = query.order_by(ScoringFeedback.created_at.desc()).limit(limit).all()
    lead_ids = {str(f.lead_id) for f in items}
    names: dict = {}
    if lead_ids:
        rows = db.query(Lead.id, Lead.company_name).filter(
            Lead.id.in_(lead_ids),
        ).all()
        names = {str(r[0]): r[1] for r in rows}

    return [
        ScoreFeedbackItem(
            id=str(f.id),
            lead_id=str(f.lead_id),
            company_name=names.get(str(f.lead_id)),
            campaign_id=str(f.campaign_id) if f.campaign_id else None,
            original_score=f.original_score,
            suggested_score=f.suggested_score,
            direction=f.direction.value,
            reason=f.reason,
            status=f.status.value,
            created_at=f.created_at.isoformat() if f.created_at else "",
        )
        for f in items
    ]
