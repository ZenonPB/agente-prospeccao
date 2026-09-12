"""Transições de status do CRM com invariantes em um único ponto.

Rotas não devem escrever ``lead.status`` diretamente para estados terminais.
Este serviço mantém PERDIDO e DESQUALIFICADO semanticamente distintos e encerra
a cadência antes do commit controlado pelo chamador.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import Lead, LeadStatus, LostReason, LeadActivityAction
from src.services.cadence_service import cancel_pending_for_terminal
from src.services.lead_activity_service import log_activity, log_status_change, semantic_action_for


class InvalidLeadStatusTransition(ValueError):
    """Transição que viola uma invariante comercial."""


def transition_lead_status(
    db: Session,
    lead: Lead,
    status_to: LeadStatus,
    *,
    user_id: Optional[str] = None,
    lost_reason: Optional[LostReason] = None,
    disqualification_reason: Optional[str] = None,
):
    """Aplica uma transição sem commit e devolve a atividade semântica principal.

    PERDIDO exige ``lost_reason``; qualquer outro estado limpa ``lost_reason``.
    DESQUALIFICADO nunca gera atividade LOST. Estados terminais cancelam etapas
    pendentes da cadência na mesma transação.
    """
    if status_to == LeadStatus.PERDIDO and lost_reason is None:
        raise InvalidLeadStatusTransition("Informe o motivo da perda")

    previous = lead.status
    lead.status = status_to
    lead.lost_reason = lost_reason if status_to == LeadStatus.PERDIDO else None

    if status_to == LeadStatus.PERDIDO:
        activity = log_activity(
            db,
            lead,
            action=LeadActivityAction.LOST,
            user_id=user_id,
            status_from=previous,
            status_to=status_to,
            detail=f"Lead perdido — motivo: {lost_reason.value}",
        )
        cancel_pending_for_terminal(db, lead, reason=f"lost:{lost_reason.value}")
    elif status_to == LeadStatus.DESQUALIFICADO:
        detail = "Lead desqualificado"
        if disqualification_reason and disqualification_reason.strip():
            detail += f" — motivo: {disqualification_reason.strip()}"
        activity = log_activity(
            db,
            lead,
            action=LeadActivityAction.STATUS_CHANGED,
            user_id=user_id,
            status_from=previous,
            status_to=status_to,
            detail=detail,
        )
        cancel_pending_for_terminal(db, lead, reason="disqualified")
    else:
        activity = log_status_change(
            db,
            lead,
            user_id=user_id,
            status_to=status_to,
            status_from=previous,
            detail=f"{previous.value if previous else '?'} → {status_to.value}",
        )
        semantic = semantic_action_for(status_to)
        if semantic:
            activity = log_activity(
                db,
                lead,
                action=semantic,
                user_id=user_id,
                status_from=previous,
                status_to=status_to,
                detail=status_to.value,
            )

    db.flush()
    return activity
