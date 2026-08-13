"""Auto-`PERDIDO` no encerramento da cadência (business-rules — dia 14).

Fecha o ciclo do `PERDIDO` ponta-a-ponta: o *requeue* (`requeue_service`, 90d)
é a "saída"; este job é a "entrada" — quando o **CLOSING** (dia 14) da cadência
foi enviado e o lead **não respondeu** dentro da carência, ele é marcado
`PERDIDO`/`NAO_RESPONDEU` (em vez de ficar `CONTATADO` para sempre).

Guardas (conservador):
- Só transiciona leads com status atual **`CONTATADO`** (contatado sem resposta).
  Nunca sobrescreve `RESPONDIDO`/ahead (o lead respondeu depois do envio).
- **Não** marca `opt_out` (leads que pediram para não receber mensagens).
- Carência contada a partir de `FollowUp.sent_at` do encerramento; `<= 0`
  desativa o job.
- Registra a trilha (STATUS_CHANGED + action `LOST`) — o *requeue* 90d usa essa
  trilha como data de perda.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import (
    FollowUp,
    FollowUpStatus,
    FollowUpStep,
    Lead,
    LeadActivityAction,
    LeadStatus,
    LostReason,
)
from src.services.lead_activity_service import log_activity, log_status_change

logger = logging.getLogger(__name__)


def _grace_elapsed(sent_at: Optional[datetime], now: datetime, days: int) -> bool:
    """True se a carência (dias desde o envio do encerramento) já venceu."""
    if not sent_at:
        return False
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)
    return now - sent_at >= timedelta(days=days)


def close_expired_cadences(
    db: Session,
    now: Optional[datetime] = None,
    grace_days: int = 7,
) -> int:
    """Marca `PERDIDO`/`NAO_RESPONDEU` cadências encerradas sem resposta.

    Args:
        db: Sessão ativa.
        now: Referência de "agora" (testável; default = horário UTC atual).
        grace_days: Carência em dias após o encerramento (dia 14) enviado sem
            resposta. `<= 0` desativa o job (nada é feito).

    Returns:
        Número de leads marcados `PERDIDO` neste ciclo.
    """
    if grace_days <= 0:
        return 0
    now = now or datetime.now(timezone.utc)

    closing = (
        db.query(FollowUp)
        .join(Lead, FollowUp.lead_id == Lead.id)
        .filter(
            FollowUp.step == FollowUpStep.CLOSING,
            FollowUp.status == FollowUpStatus.SENT,
            FollowUp.sent_at.isnot(None),
        )
        .all()
    )

    closed = 0
    for fu in closing:
        if not _grace_elapsed(getattr(fu, "sent_at", None), now, grace_days):
            continue
        lead = getattr(fu, "lead", None)
        if not lead:
            continue
        # Guardas decididas em Python (fácil de testar/fake): opt-out nunca é
        # marcado e status avançado (RESPONDIDO+ / reunião / proposta) nunca é
        # sobrescrito — só transiciona CONTATADO sem resposta.
        if getattr(lead, "opt_out", False):
            continue
        if lead.status != LeadStatus.CONTATADO:
            continue
        previous = lead.status
        lead.status = LeadStatus.PERDIDO
        lead.lost_reason = LostReason.NAO_RESPONDEU
        log_status_change(
            db,
            lead,
            user_id=None,
            status_to=LeadStatus.PERDIDO,
            status_from=previous,
            detail="Encerramento da cadência sem resposta (dia 14 → PERDIDO)",
        )
        log_activity(
            db,
            lead,
            action=LeadActivityAction.LOST,
            user_id=None,
            status_to=LeadStatus.PERDIDO,
            detail="PERDIDO",
        )
        closed += 1
        logger.info(
            "Lead %s marcado PERDIDO (%s → PERDIDO, encerramento sem resposta)",
            lead.id, previous.value if previous else "?",
        )

    if closed:
        db.commit()
    return closed