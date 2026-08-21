"""Inbound email — processa respostas e pedidos de STOP.

Quando a org usa um provedor de inbound (Postmark/SendGrid inbound parse,
IMAP poll, etc.) apontando para `POST /api/webhooks/email/inbound`, este
serviço:

- Detecta "STOP" (subject/body) → marca `opt_out` (do-not-contact) e cancela a cadência.
- Detecta resposta (qualquer outra) → move o lead para `RESPONDIDO`, cancela
  follow-ups pendentes (o lead respondeu — para de enviar), grava na trilha
  e cria notificação in-app para o consultor atribuído.

Sem token/secreto válido a rota é 404 — nenhum dado de terceiro é aceito.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.db.models import (
    Lead, LeadStatus, Contact, FollowUp, FollowUpStatus,
    LeadActivity, LeadActivityAction,
    Message, MessageChannel,
)

logger = logging.getLogger(__name__)

_STOP_RE = re.compile(r"(?i)\b(stop|pare|descadastr|remover?.*lista|cancelar.*envio)\b")


def _is_stop_request(subject: str = "", body: str = "") -> bool:
    text = f"{subject} {body}"
    return bool(_STOP_RE.search(text)) and any(w in text.lower() for w in ("stop", "pare", "descadastrar", "remover", "cancelar"))


def _record_response_message(
    db: Session, lead: Lead, body: str, now: datetime
) -> None:
    """Cria uma `Message` espelho (`is_response=True`) para fins de A/B.

    A variante é derivada da última `Message` enviada do lead antes do
    `now`. Isso permite ao `AnalyticsService.message_variants()` medir
    resposta por variante sem proxy pelo status do funil (que mistura
    todas as etapas).

    Sem `Message` enviada anterior, nenhum registro é criado.
    """
    last_sent = (
        db.query(Message)
        .filter(
            Message.lead_id == lead.id,
            Message.sent_at.isnot(None),
            Message.sent_at <= now,
        )
        .order_by(Message.sent_at.desc())
        .first()
    )
    if last_sent is None:
        return

    # Evita duplicar: se a última `Message` enviada já é uma resposta,
    # não criamos outra (ex.: webhook chamado duas vezes).
    if last_sent.is_response:
        last_sent.responded_at = now
        return

    db.add(Message(
        lead_id=lead.id,
        channel=MessageChannel.EMAIL,
        content=body or "",
        ai_generated_draft=None,
        sent_at=now,
        responded_at=now,
        is_response=True,
        tracking_token=last_sent.tracking_token,
        variant=last_sent.variant,
    ))


def process_inbound_email(db: Session, from_email: str, subject: str, body: str) -> Dict[str, bool]:
    """Processa uma resposta de e-mail. Retorna {matched, stop_requested}.

    `from_email` é normalizado (lowercase) e procurado nos contatos/e-mails
    dos leads de qualquer org. Sem match, a mensagem é ignorada (não cria
    nada) e `matched=False`.
    """
    sender = (from_email or "").strip().lower()
    if not sender:
        return {"matched": False, "stop_requested": False}

    lead = (
        db.query(Lead)
        .outerjoin(Contact, Contact.lead_id == Lead.id)
        .filter(
            or_(
                Lead.email == sender,
                Contact.email == sender,
            )
        )
        .first()
    )
    if not lead:
        logger.info("Inbound email sem lead correspondente (%s)", sender)
        return {"matched": False, "stop_requested": False}

    now = datetime.now(timezone.utc)
    stop = _is_stop_request(subject, body)

    if stop:
        # Pedido de descadastro — para qualquer envio futuro.
        lead.opt_out = True
        for fu in db.query(FollowUp).filter(
            FollowUp.lead_id == lead.id,
            FollowUp.status == FollowUpStatus.PENDING,
        ).all():
            fu.status = FollowUpStatus.SKIPPED
        log_inbound_activity(db, lead, "Opt-out por resposta STOP (inbound)", now)
        logger.info("Lead %s opt-out via inbound STOP de %s", lead.id, sender)
    else:
        # Resposta: se ainda não avançou no funil, marca RESPONDIDO e para a
        # cadência (lead respondeu — segue pelo canal humano).
        if lead.status not in (
            LeadStatus.REUNIAO_MARCADA, LeadStatus.REUNIAO_FEITA,
            LeadStatus.PROPOSTA_ENVIADA, LeadStatus.PERDIDO,
        ):
            lead.status = LeadStatus.RESPONDIDO
        lead.last_contacted_at = now
        for fu in db.query(FollowUp).filter(
            FollowUp.lead_id == lead.id,
            FollowUp.status == FollowUpStatus.PENDING,
        ).all():
            fu.status = FollowUpStatus.CANCELLED
        _record_response_message(db, lead, body or "", now)
        log_inbound_activity(db, lead, "Resposta recebida (inbound)", now)
        logger.info("Lead %s marcado RESPONDIDO via inbound de %s", lead.id, sender)

        # Notificação in-app para o consultor atribuído
        try:
            from src.services.notification_service import create_lead_responded_notification
            create_lead_responded_notification(db, lead, lead.organization_id)
        except Exception as e:
            logger.warning("Falha ao criar notificação de resposta: %s", e)

    db.commit()
    return {"matched": True, "stop_requested": stop}


def log_inbound_activity(db: Session, lead: Lead, detail: str, now: datetime) -> None:
    db.add(LeadActivity(
        lead_id=lead.id,
        action=LeadActivityAction.RESPONDED if "Resposta" in detail else LeadActivityAction.STATUS_CHANGED,
        detail=detail,
        status_to=lead.status,
        created_at=now,
    ))
