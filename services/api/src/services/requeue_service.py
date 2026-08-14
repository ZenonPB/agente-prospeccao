"""Re-enfileiramento de leads `PERDIDO` após o período de carência (90 dias).

Regra documentada em `docs/business-rules.md`. Decisão (escopo conservador —
reabrir perda deliberada não é automático):

- Só volta à fila quem foi perdido por **ausência de resposta** (`lost_reason`
  nulo ou `NAO_RESPONDEU`) e **não** pediu `opt_out`. Perdas deliberadas
  (`PRECO`/`CONCORRENTE`/`PRAZO`/`OUTRO`) permanecem perdidas.
- Destino: `NOVO` (re-entra na fila p/ nova campanha/re-scoring), `lost_reason`
  é limpo, a atribuição ao consultor é **mantida** e a transição entra na trilha.
- Data de perda: última `LeadActivity` com `status_to=PERDIDO` (exata); fallback
  `Lead.updated_at` para leads antigos sem trilha.
- Idempotente: um lead só re-enfileira uma vez (depois não é mais `PERDIDO`).
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import Lead, LeadActivity, LeadStatus, LostReason
from src.services.lead_activity_service import log_status_change

logger = logging.getLogger(__name__)

# Razões de perda que representam "ciclo encerrado sem resposta" — os únicos
# que re-enfileiram automaticamente (ver docstring do módulo).
REQUEUE_LOST_REASONS = (LostReason.NAO_RESPONDEU,)


def _is_expired(last_lost_at: Optional[datetime], now: datetime, days: int) -> bool:
    """True se o lead está em `PERDIDO` há >= `days` (função pura — testável)."""
    if not last_lost_at:
        return False
    if last_lost_at.tzinfo is None:
        last_lost_at = last_lost_at.replace(tzinfo=timezone.utc)
    return now - last_lost_at >= timedelta(days=days)


def _is_time_based_loss(reason: Optional[LostReason]) -> bool:
    """Perda baseada em tempo (ciclo encerrado sem resposta) → elegível."""
    return reason is None or reason in REQUEUE_LOST_REASONS


def requeue_expired_lost(
    db: Session,
    now: Optional[datetime] = None,
    days: int = 90,
) -> int:
    """Re-enfileira (`PERDIDO` → `NOVO`) os leads vencidos pela carência.

    Args:
        db: Sessão ativa.
        now: Referência de "agora" (testável; default = horário UTC atual).
        days: Carência em dias. `<= 0` desativa o job (nada é feito).

    Returns:
        Número de leads re-enfileirados neste ciclo.
    """
    if days <= 0:
        return 0
    now = now or datetime.now(timezone.utc)

    # Data de perda exata: última LeadActivity com status_to=PERDIDO.
    last_lost_rows = (
        db.query(
            LeadActivity.lead_id,
            func.max(LeadActivity.created_at).label("lost_at"),
        )
        .filter(LeadActivity.status_to == LeadStatus.PERDIDO)
        .group_by(LeadActivity.lead_id)
        .all()
    )
    lost_at_by_lead = {row.lead_id: row.lost_at for row in last_lost_rows}

    candidates = (
        db.query(Lead)
        .filter(Lead.status == LeadStatus.PERDIDO)
        .all()
    )

    requeued = 0
    for lead in candidates:
        # Elegibilidade decidida em Python (fácil de testar/fake): opt-out nunca
        # volta e perda deliberada (PRECO/CONCORRENTE/PRAZO/OUTRO) não volta.
        if getattr(lead, "opt_out", False):
            continue
        if not _is_time_based_loss(lead.lost_reason):
            continue
        lost_at = lost_at_by_lead.get(lead.id) or getattr(lead, "updated_at", None)
        if not _is_expired(lost_at, now, days):
            continue
        previous = lead.status
        lead.status = LeadStatus.NOVO
        lead.lost_reason = None
        log_status_change(
            db,
            lead,
            user_id=None,
            status_to=LeadStatus.NOVO,
            status_from=previous,
            detail="Re-enfileirado após o período de carência (PERDIDO → NOVO)",
        )
        requeued += 1
        logger.info(
            "Lead %s re-enfileirado após %d dias em PERDIDO (%s → NOVO)",
            lead.id, days, previous.value if previous else "?",
        )

    if requeued:
        db.commit()
    return requeued