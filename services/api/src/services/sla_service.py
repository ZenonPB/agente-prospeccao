"""Serviço de SLA e lembretes para leads parados.

Regras configuráveis por organização (`Organization.sla_*_days`) que
alimentam o painel "Ações de hoje" e os alertas do kanban:

- `QUALIFICADO_NO_CONTACT`: apto sem contato há N dias → alerta.
- `RESPONDIDO_NO_NEXT_ACTION`: respondeu, mas sem próximo passo agendado
  (ou vencido) há N dias → lembrete.
- `OPENED_NO_RESPONSE`: abriu a mensagem (tracking 4.2) e não respondeu há
  N dias → nudge.

Todas as consultas são `organization_id`-scoped e respeitam o escopo do
membro (CONSULTOR vê apenas os próprios leads + não atribuídos).
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from src.db.models import (
    Lead,
    LeadStatus,
    Message,
    Organization,
)

logger = logging.getLogger(__name__)


# Alertas que não fazem sentido para leads já "mortos"/encerrados.
_CLOSED_STATUSES = (
    LeadStatus.REUNIAO_MARCADA,
    LeadStatus.REUNIAO_FEITA,
    LeadStatus.PROPOSTA_ENVIADA,
    LeadStatus.PERDIDO,
    LeadStatus.DESQUALIFICADO,
)


def _apply_scope(member, query):
    """Aplica o escopo de CONSULTOR (próprios + não atribuídos) à query.

    ANALYST/MANAGER/owner/admin não são filtrados (acesso total). Reusa o
    mesmo comportamento de `consultant_lead_scope` sem duplicar regra.
    """
    from src.services.org_service import consultant_lead_scope
    return consultant_lead_scope(member, query)


def _alert(lead: Lead, alert_type: str, label: str, days: int,
           anchor: datetime | None = None, extra: dict | None = None) -> dict:
    return {
        "id": str(lead.id),
        "company_name": lead.company_name,
        "city": lead.city,
        "state": lead.state,
        "status": lead.status.value if lead.status else None,
        "qualification_score": lead.qualification_score,
        "assigned_to_name": lead.assigned_to.name if lead.assigned_to else None,
        "alert_type": alert_type,
        "alert_label": label,
        "days_since": days,
        "last_contacted_at": lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
        "next_action_at": lead.next_action_at.isoformat() if lead.next_action_at else None,
        **({} if extra is None else extra),
    }


def _days_since(anchor: datetime, now: datetime) -> int:
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    return max(0, int((now - anchor).total_seconds() // 86400))


def compute_sla_alerts(
    db: Session,
    org_id,
    member,
    limit: int = 50,
) -> list:
    """Calcula os alertas de SLA da organização no momento atual.

    Returns:
        list[dict] ordenada por criticidade (dias desde o acionamento do
        alerta, maior primeiro).
    """
    now = datetime.now(timezone.utc)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    q_days = org.sla_qualified_no_contact_days if org else 5
    r_days = org.sla_responded_no_next_action_days if org else 2
    o_days = org.sla_opened_no_response_days if org else 2

    alerts: list = []
    base = db.query(Lead).filter(Lead.organization_id == org_id, Lead.opt_out.is_(False))

    # Regra QUALIFICADO sem contato há N dias (âncora: último contato ou criação).
    cutoff_q = now - timedelta(days=q_days)
    q_base = _apply_scope(member, base.filter(Lead.status == LeadStatus.QUALIFICADO))
    for lead in q_base.filter(
        func.coalesce(Lead.last_contacted_at, Lead.created_at) < cutoff_q
    ).limit(limit).all():
        anchor = lead.last_contacted_at or lead.created_at or cutoff_q
        alerts.append(_alert(
            lead, "QUALIFICADO_NO_CONTACT",
            f"Apto sem contato há {_days_since(anchor, now)} dia(s)",
            _days_since(anchor, now),
            anchor,
        ))

    # Regra RESPONDIDO sem próximo passo agendado/vencido há N dias.
    cutoff_r = now - timedelta(days=r_days)
    r_base = _apply_scope(member, base.filter(
        Lead.status == LeadStatus.RESPONDIDO,
        or_(
            Lead.next_action_at.is_(None),
            Lead.next_action_at <= now,
        ),
        func.coalesce(Lead.updated_at, Lead.created_at) < cutoff_r,
    ))
    for lead in r_base.limit(limit).all():
        anchor = lead.updated_at or lead.created_at or cutoff_r
        alerts.append(_alert(
            lead, "RESPONDIDO_NO_NEXT_ACTION",
            f"Respondeu e aguarda próximo passo há {_days_since(anchor, now)} dia(s)",
            _days_since(anchor, now),
            anchor,
        ))

    # Regra ABRIU e não respondeu há N dias (âncora: última abertura).
    cutoff_o = now - timedelta(days=o_days)
    opened_sub = (
        db.query(Message.lead_id.label("lead_id"), func.max(Message.opened_at).label("last_opened"))
        .filter(Message.opened_at.isnot(None))
        .group_by(Message.lead_id)
        .subquery()
    )
    o_base = _apply_scope(member, base.filter(
        Lead.status.notin_([*_CLOSED_STATUSES, LeadStatus.RESPONDIDO]),
    ))
    for lead, last_opened in (
        o_base.join(opened_sub, opened_sub.c.lead_id == Lead.id)
        .filter(opened_sub.c.last_opened < cutoff_o)
        .limit(limit)
        .all()
    ):
        anchor = last_opened or cutoff_o
        alerts.append(_alert(
            lead, "OPENED_NO_RESPONSE",
            f"Abriu a mensagem e não respondeu há {_days_since(anchor, now)} dia(s)",
            _days_since(anchor, now),
            anchor,
            extra={"opened_at": anchor.isoformat() if anchor else None},
        ))

    alerts.sort(key=lambda a: a["days_since"], reverse=True)
    return alerts