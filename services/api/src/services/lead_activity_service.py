"""Serviço de trilha de atividades do lead.

Concentra a gravação de `LeadActivity` para todas as mudanças relevantes
(atribuição, status, mensagem, contato, reunião, conversão). Usado pelas
rotas da API e pelo pipeline — evita duplicação de lógica de logging.
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from src.db.models import (
    Lead,
    LeadActivity,
    LeadActivityAction,
    LeadStatus,
)

logger = logging.getLogger(__name__)


def log_activity(
    db: Session,
    lead: Lead,
    action: LeadActivityAction,
    user_id: Optional[str] = None,
    status_from: Optional[LeadStatus] = None,
    status_to: Optional[LeadStatus] = None,
    detail: Optional[str] = None,
) -> LeadActivity:
    """Registra uma atividade na trilha do lead.

    Args:
        db: Sessão ativa.
        lead: Lead afetado.
        action: Tipo de ação (LeadActivityAction).
        user_id: Quem executou (nullable — pipeline/automático).
        status_from/to: Transição de status (só para STATUS_CHANGED).
        detail: Descrição livre do que aconteceu.

    Returns:
        LeadActivity criada (não commita — quem chama decide o flush/commit).
    """
    activity = LeadActivity(
        lead_id=lead.id,
        user_id=user_id,
        action=action,
        status_from=status_from,
        status_to=status_to,
        detail=detail,
    )
    db.add(activity)
    return activity


def log_status_change(
    db: Session,
    lead: Lead,
    user_id: Optional[str],
    status_to: LeadStatus,
    status_from: Optional[LeadStatus] = None,
    detail: Optional[str] = None,
) -> LeadActivity:
    """Registra mudança de status, capturando o status anterior.

    `status_from` deve ser o status ANTES da mudança (o caller captura antes
    de setar `lead.status`). Se não informado, usa `lead.status` atual.
    """
    return log_activity(
        db,
        lead,
        action=LeadActivityAction.STATUS_CHANGED,
        user_id=user_id,
        status_from=status_from if status_from is not None else lead.status,
        status_to=status_to,
        detail=detail,
    )


def semantic_action_for(status: LeadStatus) -> Optional[LeadActivityAction]:
    """Mapeia um status de destino para a action comercial correspondente.

    Além da `STATUS_CHANGED` genérica, status com significado
    comercial gravam uma action específica na trilha — base para o dashboard
    "taxa de acerto do score" (conversão por faixa) e para calibrar threshold.
    Retorna `None` para status sem significado de outcome.
    """
    return {
        LeadStatus.CONTATADO: LeadActivityAction.CONTACTED,
        LeadStatus.RESPONDIDO: LeadActivityAction.RESPONDED,
        LeadStatus.REUNIAO_MARCADA: LeadActivityAction.MEETING_SCHEDULED,
        LeadStatus.PROPOSTA_ENVIADA: LeadActivityAction.PROPOSAL_SENT,
        LeadStatus.PERDIDO: LeadActivityAction.LOST,
    }.get(status)
