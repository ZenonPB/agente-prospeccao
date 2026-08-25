"""CadenceService — cadência de follow-up de um lead.

Sequência dia 0/3/7/14 (`FollowUpStep`), conforme `docs/business-rules.md`.
O conteúdo das etapas é gerado pelo `OutreachService` (ou fornecido no
start) e persistido em `follow_ups`, pronto para envio.

Envio:
- **Humano-no-loop (default):** o consultor envia cada etapa pela UI
  (`send_step`). Nenhum e-mail sai automaticamente sem ação humana.
- **Automático (opt-in):** se a org tem `auto_send_email=True`, o scheduler
  (`run_due`) envia quando `scheduled_at` vence, respeitando `opt_out`.
- Leads com `opt_out` têm etapas pendentes marcadas `SKIPPED` e nunca
  recebem envio automático (do-not-contact).
- Bounce: falha transitória (4xx/rede) re-tenta até
  `MAX_ATTEMPTS`; bounce permanente (5xx) marca a etapa `CANCELLED` e
  suprime o endereço em `email_suppressions`.
- Threading: cada follow-up referencia o `Message-ID` da etapa
  anterior e a **cadeia completa** de `Message-ID`s em `References`, para as
  respostas formarem conversa (o que os clients de e-mail exigem).

O envio efetivo vai via `email_service.send_email` (SMTP ou dry-run em dev).
"""
import logging
import math
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.services.observability import log_event
from src.db.models import (
    FollowUp,
    FollowUpStatus,
    FollowUpStep,
    Lead,
    LeadStatus,
    ContactRole,
    Message,
    MessageChannel,
    Organization,
    OrganizationMember,
    User,
    EmailSuppression,
    LeadActivity,
    LeadActivityAction,
)

logger = logging.getLogger(__name__)

# Máximo de tentativas para falhas transitórias antes de cancelar a etapa.
MAX_ATTEMPTS = 3


DEFAULT_CADENCE_DAYS = [0, 3, 7, 14]


def _normalize_cadence_days(day_offsets) -> List[int]:
    """Valida a lista de dias do acompanhamento (4 inteiros >= 0).

    Entrada inválida → fallback para o calendário padrão (0/3/7/14). Nunca
    quebra o agendamento.
    """
    if (
        isinstance(day_offsets, (list, tuple))
        and len(day_offsets) == 4
        and all(isinstance(d, int) and d >= 0 for d in day_offsets)
    ):
        return list(day_offsets)
    return DEFAULT_CADENCE_DAYS


def schedule_cadence(
    db: Session,
    lead: Lead,
    messages: dict,
    organization: Optional[Organization] = None,
    user_id: Optional[str] = None,
    day_offsets: Optional[List[int]] = None,
) -> List[FollowUp]:
    """Cria as 4 etapas da cadência a partir das mensagens.

    `messages` deve conter as chaves do OutreachService:
    `subject`, `body_opening`, `followup_1`, `followup_2`, `closing`.

    `day_offsets` (opcional) define os dias das mensagens — ex. [0, 7, 30, 60]
    para ciclos industriais longos. Ausente/inválido → 0/3/7/14.

    Etapas anteriores pendentes são canceladas (reagendamento limpo).
    """
    now = datetime.now(timezone.utc)
    days = _normalize_cadence_days(day_offsets)

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
        # Ordem de chegada no dict = dia da mensagem correspondente.
        offset = days[len(created)]
        scheduled = now + timedelta(days=offset)
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
        detail=f"Cadência agendada: dias {', '.join(str(d) for d in days)}",
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
    # e-mail heurístico (adivinhado) nunca vai sozinho.
    require_verified = user_id is None
    sent_to = _recipients_so_far(db, follow_up.lead_id)
    to_email = _recipient_email(
        lead,
        require_verified=require_verified,
        step=follow_up.step,
        sent_to=sent_to,
    )
    if not to_email:
        logger.info("Lead %s sem e-mail — etapa %s pulada (sem destino)",
                    lead.id if lead else follow_up.lead_id, follow_up.step.value)
        log_event(
            "cadence_skipped",
            lead_id=str(follow_up.lead_id),
            organization_id=str(lead.organization_id) if lead and lead.organization_id else None,
            reason="no_recipient",
            step=follow_up.step.value,
        )
        follow_up.status = FollowUpStatus.SKIPPED
        db.commit()
        return False

    # Supressão por bounce permanente: endereço já queimou — não re-tentar.
    if db.query(EmailSuppression.id).filter(EmailSuppression.email == to_email).first():
        logger.info("E-mail %s em supressão (bounce) — etapa %s cancelada", to_email, follow_up.step.value)
        follow_up.status = FollowUpStatus.CANCELLED
        db.commit()
        return False

    # Remetente: por consultor → org → global. O consultor que
    # "dono" do lead envia do próprio e-mail da org, preservando a reputação.
    org = None
    if lead and lead.organization_id:
        org = db.query(Organization).filter(Organization.id == lead.organization_id).first()
    from_email = _resolve_from_email(db, lead, org)
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
        follow_up.recipient = to_email
        follow_up.message_id = result.message_id
        db.commit()

        msg = Message(
            lead_id=follow_up.lead_id,
            channel=MessageChannel.EMAIL,
            content=follow_up.content,
            ai_generated_draft=follow_up.content,
            sent_at=follow_up.sent_at,
            tracking_token=follow_up.tracking_token,
            variant=follow_up.variant,
        )
        db.add(msg)
        log_cadence_event(
            db, lead,
            action=LeadActivityAction.CONTACTED,
            user_id=user_id,
            detail=f"Enviado: {follow_up.step.label} → {to_email}",
        )
        # Primeiro contato via cadência move o lead para CONTATADO.
        if lead and lead.status in (
            LeadStatus.NOVO, LeadStatus.ANALISADO,
            LeadStatus.QUALIFICADO, LeadStatus.DESQUALIFICADO,
        ):
            lead.status = LeadStatus.CONTATADO
        db.commit()
        log_event(
            "cadence_sent",
            lead_id=str(follow_up.lead_id),
            organization_id=str(lead.organization_id) if lead and lead.organization_id else None,
            user_id=str(user_id) if user_id else None,
            step=follow_up.step.value,
            message_id=str(result.message_id) if result.message_id else None,
        )
        return True

    # Falha: classifica em permanente (5xx → supressão + cancelamento) ou
    # transitória (4xx/rede → re-tenta até MAX_ATTEMPTS).
    if result.permanent:
        logger.warning("Bounce permanente %s — etapa %s cancelada e endereço suprimido",
                       to_email, follow_up.step.value)
        log_event(
            "cadence_bounced",
            lead_id=str(follow_up.lead_id),
            organization_id=str(lead.organization_id) if lead and lead.organization_id else None,
            reason=(result.error or "bounce permanente")[:255],
            step=follow_up.step.value,
        )
        follow_up.status = FollowUpStatus.CANCELLED
        db.commit()
        try:
            db.add(EmailSuppression(
                email=to_email,
                organization_id=lead.organization_id if lead else None,
                reason=(result.error or "bounce permanente")[:255],
            ))
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
      que é o que o Gmail/Exchange exigem para agrupar a conversa.
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
    """Registra opt-out (do-not-contact): cancela etapas pendentes e impede novos envios."""
    lead.opt_out = True
    for fu in db.query(FollowUp).filter(
        FollowUp.lead_id == lead.id,
        FollowUp.status == FollowUpStatus.PENDING,
    ).all():
        fu.status = FollowUpStatus.SKIPPED
    db.commit()


def _resolve_from_email(db: Session, lead: Optional[Lead], org: Optional[Organization]) -> Optional[str]:
    """Resolve o remetente de um envio, em ordem de precedência:

    1. `OrganizationMember.email_from` do consultor que é dono do lead
       (remetente dedicado — preserva a reputação individual do vendedor);
    2. `Organization.email_from` (remetente da org);
    3. `None` → a `email_service` usa o global (`SMTP_FROM_EMAIL`).
    """
    if lead and lead.assigned_to_id and lead.organization_id:
        member = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == lead.organization_id,
            OrganizationMember.user_id == lead.assigned_to_id,
        ).first()
        if member and member.email_from:
            return member.email_from
    if org and org.email_from:
        return org.email_from
    return None


def _parse_hhmm(value: Optional[str], default_minutes: int) -> int:
    """Converte "HH:MM" em minutos desde 00:00. Valor inválido → default."""
    try:
        h, m = value.split(":")
        return int(h) * 60 + int(m)
    except (AttributeError, TypeError, ValueError):
        return default_minutes


def _window_state(org: Optional[Organization], now_local: datetime) -> Tuple[bool, int]:
    """Avalia a janela de espalhamento da org e deriva o teto por hora.

    A janela (`send_window_start`/`send_window_end`, HH:MM) é interpretada no
    fuso **local do servidor**. Fora da janela → retorna `(False, 0)`, e o
    `run_due` posterga os envios (as etapas ficam PENDING até a próxima poll).

    O teto por hora é `ceil(limite_diário * 60 / minutos_da_janela)` — espalha
    os envios ao longo do dia em vez de disparar tudo de uma vez. Janela
    invertida/inválida vira dia inteiro (sem restrição horária).
    """
    limit = _org_daily_limit(org)
    start = _parse_hhmm(org.send_window_start if org else None, 9 * 60)
    end = _parse_hhmm(org.send_window_end if org else None, 17 * 60)
    minutes = end - start
    if minutes <= 0:
        # Janela inválida/invertida → sem restrição de horário, teto diário só.
        return True, max(1, math.ceil(limit / 24.0))

    now_minutes = now_local.hour * 60 + now_local.minute
    within = start <= now_minutes < end
    hourly_cap = max(1, math.ceil(limit * 60 / minutes))
    return within, hourly_cap


def _org_daily_limit(org: Optional[Organization]) -> int:
    """Teto diário da org; fallback para o default global do settings."""
    if org and org.daily_email_limit and org.daily_email_limit > 0:
        return org.daily_email_limit
    return settings.DAILY_EMAIL_LIMIT


def sends_today(db: Session, org_id, now_local: Optional[datetime] = None) -> Tuple[int, int]:
    """Conta envios da org hoje (local) e na hora atual (para o teto horário).

    Conta `Message` criados pela cadência (com `sent_at` em UTC) cujo lead
    pertence à org. Retorna `(total_hoje, enviados_na_hora)`.
    """
    now_local = now_local or datetime.now().astimezone()
    day_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    hour_start = now_local.replace(minute=0, second=0, microsecond=0).astimezone(timezone.utc)

    base = (
        db.query(func.count(Message.id))
        .join(Lead, Message.lead_id == Lead.id)
        .filter(Lead.organization_id == org_id)
    )
    today = base.filter(Message.sent_at >= day_start).scalar() or 0
    hour = base.filter(Message.sent_at >= hour_start).scalar() or 0
    return int(today), int(hour)


def run_due(db: Session) -> Tuple[int, int]:
    """Envia automaticamente as etapas vencidas de orgs com `auto_send_email`.

    Rodado periodicamente pelo scheduler (main.py). Respeita:
    - opt-out e `email_verified` (via `send_step`);
    - **throttling**: teto diário por org (`daily_email_limit`),
      janela de espalhamento (`send_window_start/end`) e teto por hora;
    - etapas que não couberem no orçamento do dia/hora **permanecem PENDING**
      (são postergadas para a próxima poll — nunca marcadas como falha).

    Retorna `(enviadas, postergadas)`.
    """
    now_utc = datetime.now(timezone.utc)
    now_local = datetime.now().astimezone()
    due = (
        db.query(FollowUp)
        .join(Lead, FollowUp.lead_id == Lead.id)
        .join(Organization, Lead.organization_id == Organization.id)
        .filter(
            (FollowUp.status == FollowUpStatus.PENDING)
            & (FollowUp.scheduled_at <= now_utc)
            & (Lead.opt_out.is_(False))
            & (Organization.auto_send_email.is_(True))
        )
        .order_by(FollowUp.scheduled_at.asc())
        .all()
    )

    by_org: "OrderedDict[str, List[FollowUp]]" = OrderedDict()
    for fu in due:
        org_id = fu.lead.organization_id if fu.lead else None
        if org_id:
            by_org.setdefault(str(org_id), []).append(fu)

    sent_count = 0
    deferred = 0
    for org_id, follow_ups in by_org.items():
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            continue
        limit = _org_daily_limit(org)
        sent_today, sent_hour = sends_today(db, org_id, now_local)
        within_window, hourly_cap = _window_state(org, now_local)
        budget = limit - sent_today
        sent_in_org = 0

        for fu in follow_ups:
            # Tetos diário e horário; fora da janela → posterga.
            if sent_in_org >= budget:
                deferred += 1
                continue
            if not within_window:
                deferred += 1
                continue
            if (sent_hour + sent_in_org) >= hourly_cap:
                deferred += 1
                continue
            try:
                if send_step(db, fu):
                    sent_count += 1
                    sent_in_org += 1
            except Exception as e:
                logger.error("Falha ao enviar follow-up %s do lead %s: %s",
                             fu.step.value, fu.lead_id, e)
    return sent_count, deferred


def _role_rank(contact) -> int:
    """Prioridade de autoridade do decisor (menor = mais sênior)."""
    order = {
        ContactRole.SOCIO: 0,
        ContactRole.CEO: 1,
        ContactRole.DIRETOR: 2,
        ContactRole.ADMINISTRADOR: 3,
        ContactRole.OUTRO: 4,
    }
    return order.get(getattr(contact, "role", None), 5)


def _candidate_emails(lead: Optional[Lead], require_verified: bool = False) -> List[str]:
    """Destinatários candidatos em ordem de prioridade.

    E-mail direto do lead primeiro, depois os contatos ordenados por
    autoridade (sócio/CEO antes de administrador), com o contato primário
    à frente dos demais do mesmo nível. O gate `require_verified`
    (envio automático) vale para os contatos — o e-mail heurístico só sai
    por ação humana explícita.
    """
    if not lead:
        return []
    candidates: List[str] = []
    if lead.email:
        candidates.append(lead.email)
    contacts = sorted(
        [c for c in (lead.contacts or []) if c.email],
        key=lambda c: (_role_rank(c), not bool(c.is_primary)),
    )
    for c in contacts:
        if require_verified and not getattr(c, "email_verified", False):
            continue
        email = (c.email or "").strip()
        if email and email not in candidates:
            candidates.append(email)
    return candidates


# Etapas que escalam para um decisor diferente do que recebeu a abertura:
# nos ciclos industriais, follow-up tardio e encerramento ganham resposta
# quando chegam a quem decide, não só a quem atende.
_ESCALATION_STEPS = {FollowUpStep.FOLLOWUP_2, FollowUpStep.CLOSING}


def _planned_recipient(
    lead: Optional[Lead],
    step: Optional[FollowUpStep] = None,
    require_verified: bool = False,
    sent_to: Optional[List[str]] = None,
) -> Optional[str]:
    """Destinatário da etapa.

    Abertura/followup_1 vão para o decisor principal; FOLLOWUP_2/CLOSING
    tentam escalar para outro contato de autoridade igual ou superior
    (ex.: compras → diretoria). Sem alternativo elegível, mantém o
    principal. `sent_to` lista quem já recebeu etapas anteriores.
    """
    candidates = _candidate_emails(lead, require_verified=require_verified)
    if not candidates:
        return None
    primary = candidates[0]
    if step is None or step not in _ESCALATION_STEPS:
        return primary
    already = set(sent_to or [])
    for email in candidates[1:]:
        if email not in already:
            return email
    return primary


def _recipients_so_far(db: Session, lead_id: str) -> List[str]:
    """E-mails já usados nas etapas SENT desta cadência."""
    rows = (
        db.query(FollowUp.recipient)
        .filter(
            FollowUp.lead_id == lead_id,
            FollowUp.status == FollowUpStatus.SENT,
        )
        .all()
    )
    seen: List[str] = []
    for (email,) in rows:
        if email and email not in seen:
            seen.append(email)
    return seen


def _recipient_email(
    lead: Optional[Lead],
    require_verified: bool = False,
    step: Optional[FollowUpStep] = None,
    sent_to: Optional[List[str]] = None,
) -> Optional[str]:
    return _planned_recipient(
        lead,
        step=step,
        require_verified=require_verified,
        sent_to=sent_to,
    )


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
