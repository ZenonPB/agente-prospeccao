"""Inbound email — processa respostas e pedidos de STOP com isolamento de tenant.

O chamador precisa resolver a organização antes de entrar neste serviço. A busca
por remetente é sempre confinada a ``organization_id``; um endereço igual em duas
organizações nunca pode deslocar uma resposta para o tenant errado.

Quando o mesmo endereço aparece em mais de um lead da mesma organização, a
resolução usa a cadência efetivamente enviada para aquele endereço. Se ainda
houver ambiguidade, falha fechada e não altera nenhum lead.
"""
import logging
import re
from datetime import datetime, timezone
from typing import Dict

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
    return bool(_STOP_RE.search(text)) and any(
        word in text.lower()
        for word in ("stop", "pare", "descadastrar", "remover", "cancelar")
    )


def _resolve_lead_for_sender(db: Session, organization_id, sender: str):
    """Resolve o lead sem escolher arbitrariamente entre candidatos.

    O outer join pode repetir o mesmo Lead quando mais de um Contact possui o
    endereço. A deduplicação por id é feita em memória para manter a consulta
    simples e o contrato testável. Se houver leads distintos, só aceitamos o
    que possui o envio mais recente da nossa própria cadência ao remetente.
    Empate/ausência de envio permanece ambíguo e falha fechado.
    """
    rows = (
        db.query(Lead)
        .outerjoin(Contact, Contact.lead_id == Lead.id)
        .filter(
            Lead.organization_id == organization_id,
            or_(Lead.email == sender, Contact.email == sender),
        )
        .all()
    )
    candidates = list({row.id: row for row in rows}.values())
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    candidate_ids = [row.id for row in candidates]
    sent = (
        db.query(FollowUp)
        .filter(
            FollowUp.lead_id.in_(candidate_ids),
            FollowUp.status == FollowUpStatus.SENT,
            FollowUp.recipient == sender,
            FollowUp.sent_at.isnot(None),
        )
        .order_by(FollowUp.sent_at.desc())
        .limit(2)
        .all()
    )
    if not sent:
        logger.warning(
            "Inbound ambíguo na organização %s: remetente aparece em %d leads e não há envio correlacionável",
            organization_id,
            len(candidates),
        )
        return None

    newest = sent[0]
    if len(sent) > 1 and sent[1].sent_at == newest.sent_at and sent[1].lead_id != newest.lead_id:
        logger.warning(
            "Inbound ambíguo na organização %s: dois leads possuem envio igualmente recente para o remetente",
            organization_id,
        )
        return None

    return next((row for row in candidates if row.id == newest.lead_id), None)


def _record_response_message(db: Session, lead: Lead, body: str, now: datetime) -> None:
    """Cria uma ``Message`` espelho para atribuição e análise de resposta."""
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
        tracking_token=None,
        variant=last_sent.variant,
    ))


def _pause_engagement(db: Session, organization_id, lead: Lead, *, stop: bool) -> None:
    """Mantém o motor novo coerente com o inbound sem criar nova transação."""
    try:
        from src.services.engagement_service import SequenceService

        SequenceService(db, organization_id).pause_for_lead(
            lead.id,
            "UNSUBSCRIBE" if stop else "REPLY_RECEIVED",
            terminal=stop,
        )
    except Exception as exc:  # sequência não pode invalidar um inbound legítimo
        logger.warning("Falha ao pausar engagement do lead %s: %s", lead.id, exc)


def process_inbound_email(
    db: Session,
    *,
    organization_id,
    from_email: str,
    subject: str,
    body: str,
) -> Dict[str, bool]:
    """Processa uma resposta de e-mail dentro de uma organização já autenticada.

    Retorna ``{matched, stop_requested}``. Nenhum ``db.add``/``commit`` ocorre
    quando o remetente não é encontrado ou não pode ser atribuído de forma
    determinística dentro da organização resolvida.
    """
    if organization_id is None:
        raise ValueError("organization_id é obrigatório para inbound")

    sender = (from_email or "").strip().lower()
    if not sender:
        return {"matched": False, "stop_requested": False}

    lead = _resolve_lead_for_sender(db, organization_id, sender)
    if not lead:
        logger.info("Inbound email sem lead atribuível na organização %s", organization_id)
        return {"matched": False, "stop_requested": False}

    if str(lead.organization_id) != str(organization_id):
        db.rollback()
        logger.error("Inbound recusado por divergência de tenant no lead %s", lead.id)
        return {"matched": False, "stop_requested": False}

    now = datetime.now(timezone.utc)
    stop = _is_stop_request(subject, body)

    if stop:
        lead.opt_out = True
        for follow_up in db.query(FollowUp).filter(
            FollowUp.lead_id == lead.id,
            FollowUp.status == FollowUpStatus.PENDING,
        ).all():
            follow_up.status = FollowUpStatus.SKIPPED
        _pause_engagement(db, organization_id, lead, stop=True)
        log_inbound_activity(db, lead, "Opt-out por resposta STOP (inbound)", now)
        logger.info("Lead %s opt-out via inbound", lead.id)
    else:
        if lead.status not in (
            LeadStatus.REUNIAO_MARCADA,
            LeadStatus.REUNIAO_FEITA,
            LeadStatus.PROPOSTA_ENVIADA,
            LeadStatus.PERDIDO,
            LeadStatus.DESQUALIFICADO,
        ):
            lead.status = LeadStatus.RESPONDIDO
        lead.last_contacted_at = now
        for follow_up in db.query(FollowUp).filter(
            FollowUp.lead_id == lead.id,
            FollowUp.status == FollowUpStatus.PENDING,
        ).all():
            follow_up.status = FollowUpStatus.CANCELLED
        _pause_engagement(db, organization_id, lead, stop=False)
        _record_response_message(db, lead, body or "", now)
        log_inbound_activity(db, lead, "Resposta recebida (inbound)", now)
        logger.info("Lead %s recebeu resposta via inbound", lead.id)

        try:
            from src.services.notification_service import create_lead_responded_notification
            create_lead_responded_notification(db, lead, lead.organization_id)
        except Exception as exc:
            logger.warning("Falha ao criar notificação de resposta: %s", exc)

    db.commit()
    return {"matched": True, "stop_requested": stop}


def log_inbound_activity(db: Session, lead: Lead, detail: str, now: datetime) -> None:
    db.add(LeadActivity(
        lead_id=lead.id,
        action=(LeadActivityAction.RESPONDED if "Resposta" in detail else LeadActivityAction.STATUS_CHANGED),
        detail=detail,
        status_to=lead.status,
        created_at=now,
    ))
