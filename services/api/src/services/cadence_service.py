"""CadenceService — cadência de follow-up de um lead (item 3.7).

Sequência dia 0/3/7/14 (`FollowUpStep`), conforme `docs/business-rules.md`.
O conteúdo das etapas é gerado pelo `OutreachService` (ou fornecido no
start) e persistido em `follow_ups`, pronto para envio.

Envio:
- **Humano-no-loop (default):** o consultor envia cada etapa pela UI
  (`send_step`). Nenhum e-mail sai automaticamente sem ação humana.
- **Automático (opt-in):** se a org tem `auto_send_email=True`, o scheduler
  (`run_due`) envia quando `scheduled_at` vence, respeitando `opt_out`.
- LGPD: leads com `opt_out` têm etapas pendentes marcadas `SKIPPED` e nunca
  recebem envio automático.
- Bounce (item 3.2): falha transitória (4xx/rede) re-tenta até
  `MAX_ATTEMPTS`; bounce permanente (5xx) marca a etapa `CANCELLED` e
  suprime o endereço em `email_suppressions`.
- Threading (item 4.1/4.4): cada follow-up referencia o `Message-ID` da etapa
  anterior e a **cadeia completa** de `Message-ID`s em `References`, para as
  respostas formarem conversa (o que os clients de e-mail exigem).

O envio efetivo vai via `email_service.send_email` (SMTP ou dry-run em dev).
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from src.db.models import (
    FollowUp,
    FollowUpStatus,
    FollowUpStep,
    Lead,
    LeadStatus,
    Message,
    MessageChannel,
    Organization,
    User,
    EmailSuppression,
    LeadActivity,
    LeadActivityAction,
)

logger = logging.getLogger(__name__)

# Máximo de tentativas para falhas transitórias antes de cancelar a etapa.
MAX_ATTEMPTS = 3


def schedule_cadence(
    db: Session,
    lead: Lead,
    messages: dict,
    organization: Optional[Organization] = None,
    user_id: Optional[str] = None,
) -> List[FollowUp]:
    """Cria as 4 etapas da cadência (dia 0/3/7/14) a partir das mensagens.

    `messages` deve conter as chaves do OutreachService:
    `subject`, `body_opening`, `followup_1`, `followup_2`, `closing`.
    Etapas anteriores pendentes são canceladas (reagendamento limpo).
    """
    now = datetime.now(timezone.utc)

    for old in db.query(FollowUp).filter(
        FollowUp.lead_id == lead.id,
        FollowUp.status == FollowUpStatus.PENDING,
    ).all():
        old.status = FollowUpStatus.CANCELLED

    steps_content = {
        FollowUpStep.OPENING: (messages.get("subject") or "", messages.get("body_opening") or ""),
        FollowUpStep.FOLLOWUP_1: (messages.get("subject") or "", messages.get("followup_1") or ""),
        FollowUpStep.FOLLOWUP_2: (messages.get("subject") or "", messages.get("followup_2") or ""),
        FollowUpStep.CLOSING: (messages.get("subject") or "", messages.get("closing") or ""),
    }

    created: List[FollowUp] = []
    for step, (subject, content) in steps_content.items():
        scheduled = now + timedelta(days=step.day_offset)
        fu = FollowUp(
            lead_id=lead.id,
            step=step,
            channel=MessageChannel.EMAIL,
            subject=subject,
            content=content or None,
            scheduled_at=scheduled,
            status=FollowUpStatus.PENDING,
        )
        db.add(fu)
        created.append(fu)

    db.commit()
    for fu in created:
        db.refresh(fu)

    log_cadence_event(
        db, lead,
        action=LeadActivityAction.MESSAGE_GENERATED,
        user_id=user_id,
        detail="Cadência agendada: dia 0/3/7/14",
    )
    db.commit()
    return created


def send_step(
    db: Session,
    follow_up: FollowUp,
    user_id: Optional[str] = None,
) -> bool:
    """Envia uma etapa da cadência (humano-no-loop ou scheduler).

    Marca como SENT, registra um `Message` no lead e uma atividade na trilha.
    Respeita `opt_out` e a lista de supressão (bounce permanente).

    Retorna True se a etapa foi enviada (ou já estava enviada).
    """
    if follow_up.status == FollowUpStatus.SENT:
        return True
    if follow_up.lead and follow_up.lead.opt_out:
        follow_up.status = FollowUpStatus.SKIPPED
        db.commit()
        return False
    if not follow_up.content:
        logger.warning("Follow-up %s do lead %s sem conteúdo — pulando",
                       follow_up.step.value, follow_up.lead_id)
        follow_up.status = FollowUpStatus.SKIPPED
        db.commit()
        return False

    from src.services.email_service import send_email

    lead = db.query(Lead).filter(Lead.id == follow_up.lead_id).first()
    # Envio automático (scheduler, sem user_id) exige e-mail verificado — um
    # e-mail heurístico (adivinhado, item 3.6) nunca vai sozinho.
    require_verified = user_id is None
    to_email = _recipient_email(lead, require_verified=require_verified)
    if not to_email:
        logger.info("Lead %s sem e-mail — etapa %s pulada (sem destino)",
                    lead.id if lead else follow_up.lead_id, follow_up.step.value)
        follow_up.status = FollowUpStatus.SKIPPED
        db.commit()
        return False

    # Supressão por bounce permanente: endereço já queimou — não re-tentar.
    if db.query(EmailSuppression.id).filter(EmailSuppression.email == to_email).first():
        logger.info("E-mail %s em supressão (bounce) — etapa %s cancelada", to_email, follow_up.step.value)
        follow_up.status = FollowUpStatus.CANCELLED
        db.commit()
        return False

    # Remetente por org (item 4.1); threading com o Message-ID da etapa anterior.
    org = None
    if lead and lead.organization_id:
        org = db.query(Organization).filter(Organization.id == lead.organization_id).first()
    from_email = (org.email_from if org and org.email_from else None)
    in_reply_to, references = _thread_headers(db, lead.id if lead else None, follow_up.step)

    # Tracking 4.2: token único da etapa (pixel/redirect); criado antes do envio.
    if not follow_up.tracking_token:
        follow_up.tracking_token = uuid.uuid4().hex
        db.flush()

    result = send_email(
        to_email,
        follow_up.subject or "",
        follow_up.content or "",
        from_email=from_email,
        in_reply_to=in_reply_to,
        references=references,
        tracking_token=follow_up.tracking_token,
    )

    follow_up.attempts = (follow_up.attempts or 0) + 1
    if result.sent:
        follow_up.sent_at = datetime.now(timezone.utc)
        follow_up.status = FollowUpStatus.SENT
        follow_up.message_id = result.message_id
        db.commit()

        msg = Message(
            lead_id=follow_up.lead_id,
            channel=MessageChannel.EMAIL,
            content=follow_up.content,
            ai_generated_draft=follow_up.content,
            sent_at=follow_up.sent_at,
            tracking_token=follow_up.tracking_token,
        )
        db.add(msg)
        log_cadence_event(
            db, lead,
            action=LeadActivityAction.CONTACTED,
            user_id=user_id,
            detail=f"Enviado: {follow_up.step.label}",
        )
        # Primeiro contato via cadência move o lead para CONTATADO.
        if lead and lead.status in (
            LeadStatus.NOVO, LeadStatus.ANALISADO,
            LeadStatus.QUALIFICADO, LeadStatus.DESQUALIFICADO,
        ):
            lead.status = LeadStatus.CONTATADO
        db.commit()
        return True

    # Falha: classifica em permanente (5xx → supressão + cancelamento) ou
    # transitória (4xx/rede → re-tenta até MAX_ATTEMPTS).
    if result.permanent:
        logger.warning("Bounce permanente %s — etapa %s cancelada e endereço suprimido",
                       to_email, follow_up.step.value)
        follow_up.status = FollowUpStatus.CANCELLED
        db.commit()
        try:
            db.add(EmailSuppression(email=to_email, reason=(result.error or "bounce permanente")[:255]))
            db.commit()
        except Exception:
            db.rollback()
            logger.warning("Falha ao registrar supressão de %s", to_email)
        return False

    follow_up.status = FollowUpStatus.PENDING
    if follow_up.attempts >= MAX_ATTEMPTS:
        logger.warning("Etapa %s do lead %s excedeu %d tentativas — cancelada",
                       follow_up.step.value, follow_up.lead_id, MAX_ATTEMPTS)
        follow_up.status = FollowUpStatus.CANCELLED
    db.commit()
    logger.info("Falha transitória no envio para %s: %s (tentativa %d/%d)",
                to_email, result.error or "erro", follow_up.attempts, MAX_ATTEMPTS)
    return False


def _thread_headers(
    db: Session,
    lead_id: Optional[str],
    step: FollowUpStep,
) -> "tuple[Optional[str], Optional[List[str]]]":
    """Busca os Message-IDs das etapas anteriores para threading completo.

    Ordem: OPENING (dia 0) → FOLLOWUP_1 (3) → FOLLOWUP_2 (7) → CLOSING (14).
    Retorna (in_reply_to, references):
    - in_reply_to = Message-ID da etapa mais recente já enviada;
    - references  = **toda a cadeia** de Message-IDs anteriores (em ordem),
      que é o que o Gmail/exchange exigem para agrupar a conversa (4.4).
    Retorna (None, None) se não houver etapa anterior enviada.
    """
    if not lead_id or step == FollowUpStep.OPENING:
        return None, None

    order = {
        FollowUpStep.OPENING: 0,
        FollowUpStep.FOLLOWUP_1: 1,
        FollowUpStep.FOLLOWUP_2: 2,
        FollowUpStep.CLOSING: 3,
    }
    prev_steps = {s: o for s, o in order.items() if o < order[step]}
    if not prev_steps:
        return None, None

    chain = (
        db.query(FollowUp.message_id)
        .filter(
            FollowUp.lead_id == lead_id,
            FollowUp.step.in_(list(prev_steps.keys())),
            FollowUp.status == FollowUpStatus.SENT,
            FollowUp.message_id.isnot(None),
        )
        .order_by(FollowUp.scheduled_at.asc())
        .all()
    )
    refs = [row[0] for row in chain]
    if not refs:
        return None, None
    return refs[-1], refs


def mark_opt_out(db: Session, lead: Lead) -> None:
    """Registra opt-out (LGPD): cancela etapas pendentes e impede novos envios."""
    lead.opt_out = True
    for fu in db.query(FollowUp).filter(
        FollowUp.lead_id == lead.id,
        FollowUp.status == FollowUpStatus.PENDING,
    ).all():
        fu.status = FollowUpStatus.SKIPPED
    db.commit()


def run_due(db: Session) -> int:
    """Envia automaticamente as etapas vencidas de orgs com `auto_send_email`.

    Rodado periodicamente pelo scheduler (main.py). Respeita opt-out. Retorna
    quantas etapas foram enviadas. Não envia nada para orgs sem opt-in.
    """
    from sqlalchemy import and_

    now = datetime.now(timezone.utc)
    due = (
        db.query(FollowUp)
        .join(Lead, FollowUp.lead_id == Lead.id)
        .join(Organization, Lead.organization_id == Organization.id)
        .filter(
            and_(
                FollowUp.status == FollowUpStatus.PENDING,
                FollowUp.scheduled_at <= now,
                Lead.opt_out.is_(False),
                Organization.auto_send_email.is_(True),
            )
        )
        .all()
    )
    sent_count = 0
    for fu in due:
        try:
            if send_step(db, fu):
                sent_count += 1
        except Exception as e:
            logger.error("Falha ao enviar follow-up %s do lead %s: %s",
                         fu.step.value, fu.lead_id, e)
    return sent_count


def _recipient_email(lead: Optional[Lead], require_verified: bool = False) -> Optional[str]:
    if not lead:
        return None
    if lead.email:
        return lead.email
    for c in lead.contacts or []:
        if not c.email:
            continue
        # Roadmap 4.1: envio automático (scheduler) exige e-mail com
        # entregabilidade passiva confirmada (`email_verified`). E-mail
        # heurístico/não verificado só sai por ação humana explícita.
        if require_verified and not getattr(c, "email_verified", False):
            continue
        return c.email
    return None


def log_cadence_event(
    db: Session,
    lead: Optional[Lead],
    action: LeadActivityAction,
    user_id: Optional[str],
    detail: str,
) -> Optional[LeadActivity]:
    if not lead:
        return None
    activity = LeadActivity(
        lead_id=lead.id,
        user_id=user_id,
        action=action,
        detail=detail,
    )
    db.add(activity)
    return activity
