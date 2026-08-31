from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from urllib.parse import quote
from datetime import datetime, timezone, timedelta
import uuid
import os
import sys
import logging

logger = logging.getLogger(__name__)

from src.db.dependencies import get_db
from src.db.models import Lead, LeadStatus, Enrichment, Contact, CompanyRecord, ContactRole, Campaign, User, Organization, OrganizationMember, LeadActivity, LeadActivityAction, Conversion, FollowUp, FollowUpStatus, FollowUpStep, Message, NegotiationStage, ContractOutcome, PostSaleChannel, LostReason
from src.auth.dependencies import get_current_user, get_user_organization, get_user_membership
from src.middleware.rate_limit import limiter
from src.services.lead_activity_service import log_activity, log_status_change, semantic_action_for
from src.services.org_service import consultant_lead_scope, is_full_access

# Importa serviços dos workers (reaproveitando a fonte única).
_workers_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "workers", "src")
sys.path.insert(0, _workers_path)
from services.cnpj_service import CnpjService  # noqa: E402
from services.outreach_service import OutreachService  # noqa: E402
from src.services.pitch_service import build_pitch_one_pager, build_site_audit  # noqa: E402
from src.services.linkedin_assist_service import linkedin_match_status  # noqa: E402
from services.enrichment_ts import freshness_snapshot, read_stamps  # noqa: E402


def _suggest_next_action_at(status: LeadStatus) -> Optional[datetime]:
    """Sugere data/hora para próxima ação baseada no estágio do funil."""
    now = datetime.now(timezone.utc)
    suggestions = {
        LeadStatus.QUALIFICADO: timedelta(days=1),
        LeadStatus.CONTATADO: timedelta(days=3),
        LeadStatus.RESPONDIDO: timedelta(days=2),
        LeadStatus.REUNIAO_MARCADA: timedelta(days=7),
        LeadStatus.REUNIAO_FEITA: timedelta(days=3),
        LeadStatus.PROPOSTA_ENVIADA: timedelta(days=5),
    }
    delta = suggestions.get(status)
    if delta:
        return now + delta
    return None

router = APIRouter(prefix="/leads", tags=["leads"])

# Status em que faz sentido registrar o funil interno de negociação
# (RD/ORÇAMENTO/RP) — a fase comercial entre responder e fechar.
NEGOTIATION_STATUSES = {
    LeadStatus.RESPONDIDO,
    LeadStatus.REUNIAO_MARCADA,
    LeadStatus.REUNIAO_FEITA,
    LeadStatus.PROPOSTA_ENVIADA,
}


class UpdateLeadStatusRequest(BaseModel):
    status: LeadStatus
    lost_reason: Optional[LostReason] = None


class UpdateLeadRequest(BaseModel):
    """Campos de trabalho do consultor + forecast (valor/previsão)."""
    notes: Optional[str] = None
    whatsapp: Optional[str] = None
    next_action_at: Optional[str] = None  # ISO datetime (tz-aware) ou null
    last_contacted_at: Optional[str] = None
    value: Optional[float] = None
    expected_close_date: Optional[str] = None
    lost_reason: Optional[LostReason] = None


class EnrichContactsRequest(BaseModel):
    cnpj: str


class GenerateMessagesRequest(BaseModel):
    channel: str = "EMAIL"  # EMAIL | WHATSAPP — afeta foco de retorno hoje
    force_regenerate: bool = False
    variants: bool = False  # True pede duas sequências A/B em uma única chamada


class RecordWhatsAppClickRequest(BaseModel):
    message_text: Optional[str] = None


def _contact_to_dict(c: Contact) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "role": c.role.value if c.role else None,
        "role_label": c.role_label,
        "email": c.email,
        "phone": c.phone,
        "document_cpf": c.document_cpf,
        "confidence": c.confidence,
        "email_verified": getattr(c, "email_verified", False),
        "email_verified_at": c.email_verified_at.isoformat() if getattr(c, "email_verified_at", None) else None,
        "linkedin_url": c.linkedin_url,
        "linkedin_confidence": c.linkedin_confidence,
        "linkedin_match_status": linkedin_match_status(
            c.linkedin_url,
            (c.raw_data or {}).get("linkedin_source") if isinstance(c.raw_data, dict) else None,
            c.linkedin_confidence,
        ),
        "is_primary": c.is_primary,
        "source": c.source,
        "raw_data": c.raw_data,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _company_record_to_dict(cr: Optional[CompanyRecord]) -> Optional[dict]:
    if not cr:
        return None
    return {
        "cnpj": cr.cnpj,
        "razao_social": cr.razao_social,
        "nome_fantasia": cr.nome_fantasia,
        "porte": cr.porte,
        "porte_label": cr.porte_label,
        "natureza_juridica": cr.natureza_juridica,
        "capital_social": float(cr.capital_social) if cr.capital_social is not None else None,
        "situacao_cadastral": cr.situacao_cadastral,
        "data_abertura": cr.data_abertura,
        "idade_anos": cr.idade_anos,
        "cnae_principal": cr.cnae_principal,
        "cnae_principal_label": cr.cnae_principal_label,
        "cnae_secundarios": cr.cnae_secundarios,
        "endereco": cr.endereco,
        "municipios_ativos": cr.municipios_ativos,
        "raw_data": cr.raw_data,
    }


def _lead_summary(lead: Lead) -> dict:
    """Resumo do lead para a listagem (sem JSONB pesado)."""
    return {
        "id": str(lead.id),
        "name": lead.name or lead.company_name,
        "company_name": lead.company_name,
        "cnpj": lead.cnpj,
        "website": lead.website,
        "phone": lead.phone,
        "whatsapp": lead.whatsapp,
        "email": lead.email,
        "category": lead.category,
        "city": lead.city,
        "state": lead.state,
        "country": lead.country,
        "google_rating": lead.google_rating,
        "google_rating_count": lead.google_rating_count,
        "google_maps_uri": lead.google_maps_uri,
        "company_linkedin_url": lead.company_linkedin_url,
        "instagram_url": lead.instagram_url,
        "status": lead.status.value if lead.status else None,
        "qualification_score": lead.qualification_score,
        "qualification_reason": lead.qualification_reason,
        "primary_need": lead.primary_need,
        "priority": lead.priority.value if lead.priority else None,
        "priority_reasoning": lead.priority_reasoning,
        "executive_summary": lead.executive_summary,
        "pitch_angle": lead.pitch_angle,
        "suggested_subject": lead.suggested_subject,
        "campaign_id": str(lead.campaign_id) if lead.campaign_id else None,
        "assigned_to_id": str(lead.assigned_to_id) if lead.assigned_to_id else None,
        "assigned_to_name": lead.assigned_to.name if lead.assigned_to else None,
        "assigned_at": lead.assigned_at.isoformat() if lead.assigned_at else None,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
        "negotiation_stage": lead.negotiation_stage.value if lead.negotiation_stage else None,
        "contract_outcome": lead.contract_outcome.value if lead.contract_outcome else None,
        "outcome_date": lead.outcome_date.isoformat() if lead.outcome_date else None,
        "post_sale_contacted_at": lead.post_sale_contacted_at.isoformat() if lead.post_sale_contacted_at else None,
        "post_sale_channel": lead.post_sale_channel.value if lead.post_sale_channel else None,
        "value": float(lead.value) if lead.value is not None else None,
        "expected_close_date": lead.expected_close_date.isoformat() if lead.expected_close_date else None,
        "lost_reason": lead.lost_reason.value if lead.lost_reason else None,
        "company_id": str(lead.company_id) if lead.company_id else None,
        "primary_person_id": str(lead.primary_person_id) if lead.primary_person_id else None,
        "company_name_3e": lead.company.company_name if lead.company else lead.company_name,
        "primary_person_name": lead.primary_person.name if lead.primary_person else None,
    }


def _lead_detail(lead: Lead, enrichment: Optional[Enrichment], include_raw: bool = False) -> dict:
    """Detalhe do lead com evidence/score_factors estruturados."""
    summary = _lead_summary(lead)
    detail = {
        "notes": lead.notes,
        "next_action_at": lead.next_action_at.isoformat() if lead.next_action_at else None,
        "last_contacted_at": lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
        "address": lead.address,
        "assigned_to_id": str(lead.assigned_to_id) if lead.assigned_to_id else None,
        "assigned_at": lead.assigned_at.isoformat() if lead.assigned_at else None,
        "contacts": [
            _contact_to_dict(c) for c in (lead.contacts or [])
        ],
        "activities": [
            {
                "id": str(a.id),
                "action": a.action.value,
                "user_id": str(a.user_id) if a.user_id else None,
                "user_name": a.user.name if a.user else None,
                "status_from": a.status_from.value if a.status_from else None,
                "status_to": a.status_to.value if a.status_to else None,
                "detail": a.detail,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in (lead.activities or [])
        ],
        "enrichment": {
            "id": str(enrichment.id),
            "lead_id": str(enrichment.lead_id),
            "website_exists": enrichment.website_exists,
            "ssl_ok": enrichment.ssl_ok,
            "https_redirect_ok": enrichment.https_redirect_ok,
            "responsive_design": enrichment.responsive_design,
            "cms": enrichment.cms,
            "lighthouse_score": enrichment.lighthouse_score,
            "seo_errors": enrichment.seo_errors,
            "load_time_ms": enrichment.load_time_ms,
            "security_issues": enrichment.security_issues,
            "created_at": enrichment.created_at.isoformat() if enrichment.created_at else None,
            "updated_at": enrichment.updated_at.isoformat() if enrichment.updated_at else None,
        } if enrichment else None,
        "enrichment_freshness": freshness_snapshot(read_stamps(lead)),
    }
    if include_raw:
        detail["score_factors"] = lead.score_factors
        detail["evidence"] = lead.evidence
        if enrichment:
            detail["enrichment"]["raw_technical_data"] = enrichment.raw_technical_data
    summary.update(detail)
    return summary


def _can_access_lead(member: OrganizationMember, lead: Lead) -> bool:
    """True se o membro pode ver/editar o lead (escopo do consultor).

    - ANALYST/MANAGER: acesso total.
    - CONSULTOR: apenas o próprio funil ou leads não atribuídos.
    """
    if is_full_access(member):
        return True
    return lead.assigned_to_id is None or lead.assigned_to_id == member.user_id


@router.get("")
def list_leads(
    status: Optional[str] = None,
    campaign_id: Optional[str] = None,
    search: Optional[str] = None,
    min_score: Optional[int] = None,
    assigned: Optional[str] = Query(None, pattern="^(me|none|any)$"),
    consultant_id: Optional[str] = None,
    next_action_before: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    query = db.query(Lead).filter(Lead.organization_id == _org.id)
    query = consultant_lead_scope(member, query)

    if status:
        status_list = [s.strip() for s in status.split(",") if s.strip()]
        try:
            enum_values = [LeadStatus(s) for s in status_list]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Status inválido: {status_list}")
        if len(enum_values) == 1:
            query = query.filter(Lead.status == enum_values[0])
        else:
            query = query.filter(Lead.status.in_(enum_values))
    if campaign_id:
        query = query.filter(Lead.campaign_id == campaign_id)
    if search:
        query = query.filter(Lead.company_name.ilike(f"%{search}%"))
    if min_score is not None:
        query = query.filter(Lead.qualification_score >= min_score)
    if consultant_id:
        # Filtro por consultor (carteira de um usuário) — limitado a quem tem
        # acesso total (ANALYST/MANAGER/owner), mesmo padrão das rotas de BI.
        if not is_full_access(member):
            raise HTTPException(status_code=403, detail="Acesso restrito a leads de outros consultores")
        try:
            consultant_uuid = uuid.UUID(consultant_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="consultant_id inválido")
        lookup = (
            db.query(OrganizationMember)
            .filter(
                OrganizationMember.organization_id == _org.id,
                OrganizationMember.user_id == consultant_uuid,
            )
            .first()
        )
        if not lookup:
            raise HTTPException(status_code=404, detail="Consultor não encontrado")
        query = query.filter(Lead.assigned_to_id == consultant_uuid)
    if assigned:
        if assigned == "me":
            query = query.filter(Lead.assigned_to_id == member.user_id)
        elif assigned == "none":
            query = query.filter(Lead.assigned_to_id.is_(None))
        elif assigned == "any":
            query = query.filter(Lead.assigned_to_id.isnot(None))
    if next_action_before:
        # Fila "ações de hoje": leads com próxima ação marcada para antes desta
        # data/hora (inclui vencidos). Data simples ("YYYY-MM-DD") vira fim do dia.
        raw = next_action_before
        if "T" not in raw and " " not in raw:
            raw = f"{raw}T23:59:59"
        query = query.filter(
            Lead.next_action_at.isnot(None),
            Lead.next_action_at <= _parse_dt(raw),
        )

    total = query.count()
    from sqlalchemy.orm import joinedload
    leads = (
        query.order_by(Lead.qualification_score.desc())
        .options(
            joinedload(Lead.assigned_to),
            joinedload(Lead.company),
            joinedload(Lead.primary_person),
        )
        .offset(offset).limit(limit).all()
    )

    return {
        "total": total,
        "leads": [_lead_summary(lead) for lead in leads],
    }


@router.get("/stats")
def lead_stats(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    base = db.query(Lead).filter(Lead.organization_id == _org.id)
    base = consultant_lead_scope(member, base)
    total = base.count()
    qualified = base.filter(Lead.status == LeadStatus.QUALIFICADO).count()
    contacted = base.filter(Lead.status == LeadStatus.CONTATADO).count()
    meetings = base.filter(Lead.status == LeadStatus.REUNIAO_MARCADA).count()
    avg_score = db.query(func.avg(Lead.qualification_score)).filter(
        Lead.organization_id == _org.id,
        (Lead.assigned_to_id == member.user_id) | (Lead.assigned_to_id.is_(None)),
    ).scalar() or 0 if not is_full_access(member) else db.query(func.avg(Lead.qualification_score)).filter(Lead.organization_id == _org.id).scalar() or 0

    by_status = {}
    for s in LeadStatus:
        count = base.filter(Lead.status == s).count()
        if count > 0:
            by_status[s.value] = count

    return {
        "total": total,
        "by_status": by_status,
        "avg_score": round(float(avg_score), 1),
        "qualified_count": qualified,
        "qualified_pct": round((qualified / total * 100), 1) if total > 0 else 0,
        "contacted_count": contacted,
        "meetings_count": meetings,
    }


@router.get("/sla-alerts")
def list_sla_alerts(
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Alertas de SLA / leads parados.

    Regras configuráveis por org: QUALIFICADO sem contato há N dias,
    RESPONDIDO sem próximo passo há N dias e lead que abriu mas não
    respondeu há N dias. Alimenta o painel "Ações de hoje".
    """
    from src.services.sla_service import compute_sla_alerts
    alerts = compute_sla_alerts(db, _org.id, member, limit=limit)
    return {"alerts": alerts}


@router.patch("/{lead_id}/status")
def update_lead_status(
    lead_id: str,
    body: UpdateLeadStatusRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    previous = lead.status
    lead.status = body.status
    if body.lost_reason is not None:
        lead.lost_reason = body.lost_reason
    log_status_change(
        db, lead, user_id=str(user.id), status_to=body.status,
        status_from=previous,
        detail=f"{previous.value if previous else '?'} → {body.status.value}",
    )
    # Grava também a action comercial correspondente (ex.: REUNIAO_MARCADA
    # -> MEETING_SCHEDULED, PROPOSTA_ENVIADA -> PROPOSAL_SENT, PERDIDO -> LOST).
    semantic = semantic_action_for(body.status)
    if semantic:
        log_activity(
            db, lead, action=semantic, user_id=str(user.id),
            status_to=body.status,
            detail=body.status.value,
        )
    db.commit()
    db.refresh(lead)

    from src.services.webhook_outbound_service import enqueue_webhook
    enqueue_webhook(
        background_tasks, db, lead.organization_id,
        event="lead.status_changed",
        data={
            "lead_id": str(lead.id),
            "company_name": lead.company_name,
            "previous_status": previous.value if previous else None,
            "status": lead.status.value,
            "lost_reason": lead.lost_reason.value if lead.lost_reason else None,
            "changed_by": str(user.id) if user else None,
            "changed_at": (lead.updated_at or datetime.now(timezone.utc)).isoformat(),
        },
    )

    return {
        "id": str(lead.id),
        "company_name": lead.company_name,
        "status": lead.status.value if lead.status else None,
        "suggested_next_action_at": _suggest_next_action_at(body.status).isoformat() if _suggest_next_action_at(body.status) else None,
    }


@router.delete("/{lead_id}")
def delete_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
    user: User = Depends(get_current_user),
):
    """Exclui um lead e seus dados relacionados (direito ao apagamento).

    Requer acesso total (ANALYST/MANAGER/owner/admin). Remove contactos,
    atividades, follow-ups, mensagens, conversões, enriquecimento e registro
    cadastral em cascata.
    """
    if not is_full_access(member):
        raise HTTPException(status_code=403, detail="Somente analista/gestor pode excluir leads")

    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    from src.db.models import (
        Message, FollowUp, Contact, LeadActivity, Conversion, Enrichment, CompanyRecord,
    )
    from sqlalchemy import delete as sa_delete

    lead_uuid = lead.id
    for model in (Message, FollowUp, Contact, LeadActivity, Conversion, Enrichment, CompanyRecord):
        db.execute(sa_delete(model).where(model.lead_id == lead_uuid))

    db.delete(lead)
    db.commit()

    logger.info("Lead %s excluído (por %s)", lead_uuid, user.email if user else "?")
    return {"message": "Lead excluído"}


def _parse_dt(value: Optional[str]):
    """Converte ISO datetime (aceita sufixo 'Z') para datetime com timezone."""
    if not value:
        return None
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Data/hora inválida: {value}")


@router.patch("/{lead_id}")
def update_lead(
    lead_id: str,
    body: UpdateLeadRequest,
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
    user: User = Depends(get_current_user),
):
    """Atualiza campos de trabalho do consultor: notas, WhatsApp, próxima ação,
    último contato. Requer acesso ao lead (escopo do consultor)."""
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    if body.notes is not None:
        lead.notes = body.notes
    if body.whatsapp is not None:
        lead.whatsapp = body.whatsapp
    if body.next_action_at is not None:
        lead.next_action_at = _parse_dt(body.next_action_at)
    if body.last_contacted_at is not None:
        lead.last_contacted_at = _parse_dt(body.last_contacted_at)
    if body.value is not None:
        lead.value = body.value
    if body.expected_close_date is not None:
        lead.expected_close_date = _parse_dt(body.expected_close_date) if body.expected_close_date else None
    if body.lost_reason is not None:
        lead.lost_reason = body.lost_reason

    db.commit()
    db.refresh(lead)
    return _lead_detail(lead, db.query(Enrichment).filter(Enrichment.lead_id == lead.id).first(), include_raw=True)


class AssignLeadRequest(BaseModel):
    assigned_to_id: Optional[str] = None


@router.patch("/{lead_id}/assign")
def assign_lead(
    lead_id: str,
    body: AssignLeadRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Atribui/desatribui um consultor ao lead (mesma organização).

    - `assigned_to_id` deve ser um usuário da mesma org (valida).
    - `null` desatribui o lead.
    - Registra ASSIGNED/UNASSIGNED na trilha.
    - CONSULTOR pode se auto-atribuir um lead não atribuído;
      não pode mexer em lead de outro consultor.
    """
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    new_assignee = None
    if body.assigned_to_id:
        new_assignee = db.query(User).filter(
            User.id == body.assigned_to_id,
        ).first()
        if not new_assignee:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        # O usuário-alvo precisa ser membro da mesma organização.
        from src.db.models import OrganizationMember
        target_member = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == _org.id,
            OrganizationMember.user_id == new_assignee.id,
        ).first()
        if not target_member:
            raise HTTPException(status_code=403, detail="Usuário não pertence à organização")

    previous = str(lead.assigned_to_id) if lead.assigned_to_id else None
    lead.assigned_to_id = new_assignee.id if new_assignee else None
    from datetime import datetime, timezone
    lead.assigned_at = datetime.now(timezone.utc) if new_assignee else None

    action = LeadActivityAction.ASSIGNED if new_assignee else LeadActivityAction.UNASSIGNED
    log_activity(
        db, lead, action=action, user_id=str(user.id),
        detail=f"Atribuído a {new_assignee.name}" if new_assignee
               else "Lead desatribuído",
    )
    db.commit()
    db.refresh(lead)

    return {
        "id": str(lead.id),
        "company_name": lead.company_name,
        "assigned_to_id": str(lead.assigned_to_id) if lead.assigned_to_id else None,
        "assigned_at": lead.assigned_at.isoformat() if lead.assigned_at else None,
        "assigned_to_name": new_assignee.name if new_assignee else None,
        "previous_assignee_id": previous,
    }


@router.get("/{lead_id}/duplicates")
def get_lead_duplicates(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Lista leads da mesma organização que provavelmente são o mesmo
    contato/empresa (CNPJ, domínio, e-mail ou LinkedIn compartilhados).

    Visibilidade do item 4.27 (versão pragmática): a unificação real
    exigiria o modelo Company/Person/Employment — adiada por enquanto.
    Aqui só detectamos e exibimos o aviso na UI do lead.
    """
    from src.services.duplicate_detection_service import find_duplicate_signals
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    candidates = (
        db.query(Lead)
        .filter(
            Lead.organization_id == _org.id,
            Lead.id != lead.id,
        )
        .all()
    )
    target_contacts = (
        db.query(Contact).filter(Contact.lead_id == lead.id).all()
    )

    # Batch prefetch de contatos (P0-1): evita N+1 queries no loop.
    all_lead_ids = [c.id for c in candidates]
    all_contacts = (
        db.query(Contact).filter(Contact.lead_id.in_(all_lead_ids)).all()
        if all_lead_ids else []
    )
    contacts_by_lead_id: dict = {}
    for ct in all_contacts:
        contacts_by_lead_id.setdefault(str(ct.lead_id), []).append(ct)

    others_payload = []
    for c in candidates:
        contacts = contacts_by_lead_id.get(str(c.id), [])
        others_payload.append({
            "id": c.id,
            "company_name": c.company_name,
            "cnpj": c.cnpj,
            "normalized_domain": c.normalized_domain,
            "contacts": [
                {"email": ct.email, "linkedin_url": ct.linkedin_url}
                for ct in contacts
            ],
        })
    target_payload = {
        "id": lead.id,
        "company_name": lead.company_name,
        "cnpj": lead.cnpj,
        "normalized_domain": lead.normalized_domain,
        "contacts": [
            {"email": ct.email, "linkedin_url": ct.linkedin_url}
            for ct in target_contacts
        ],
    }
    matches = find_duplicate_signals(target_payload, others_payload)
    return {"matches": matches, "count": len(matches)}


@router.get("/{lead_id}")
def get_lead(
    lead_id: str,
    include: Optional[str] = Query(None, description="Campos extras: raw_data"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    enrichment = db.query(Enrichment).filter(Enrichment.lead_id == lead.id).first()
    include_raw = include and "raw_data" in include.split(",")

    return _lead_detail(lead, enrichment, include_raw=include_raw)


@router.get("/{lead_id}/pitch")
def get_lead_pitch(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    enrichment = db.query(Enrichment).filter(Enrichment.lead_id == lead.id).first()
    campaign = (
        db.query(Campaign).filter(Campaign.id == lead.campaign_id).first()
        if lead.campaign_id else None
    )
    contacts = (
        db.query(Contact)
        .filter(Contact.lead_id == lead.id)
        .order_by(Contact.is_primary.desc())
        .all()
    )
    company_record = (
        db.query(CompanyRecord).filter(CompanyRecord.lead_id == lead.id).first()
    )

    return build_pitch_one_pager(lead, enrichment, campaign, contacts, company_record)


@router.post("/{lead_id}/generate-messages")
@limiter.limit("30/minute")
async def generate_messages(
    request: Request,
    lead_id: str,
    body: GenerateMessagesRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    from services.provider_client import quota_ok
    if not quota_ok(db, str(_org.id), "GROQ_API_KEY"):
        raise HTTPException(status_code=429, detail="Cota diária de IA esgotada — tente amanhã.")

    campaign = (
        db.query(Campaign).filter(Campaign.id == lead.campaign_id).first()
        if lead.campaign_id
        else None
    )
    context_service = campaign.target_service if campaign else None
    context_segment = campaign.target_segment if campaign else None

    from services.secret_service import SecretService
    from services.template_router import get_playbook_for_campaign

    keys = await SecretService.resolve_all(db, str(_org.id))
    groq = keys.get("GROQ_API_KEY")

    playbook = await get_playbook_for_campaign(
        db,
        target_service=context_service or "",
        target_segment=context_segment or "",
        explicit_template_id=str(campaign.scoring_template_id) if campaign and campaign.scoring_template_id else None,
        api_key=groq,
        organization_id=str(_org.id),
    )

    lead_dict = _build_lead_dict(lead, db)
    result = await OutreachService(api_key=groq).generate_sequence(
        lead_dict, context_service or "", context_segment or "", playbook,
        generate_variants=body.variants,
        scheduling_url=_org.scheduling_url,
        db=db,
        organization_id=str(_org.id),
    )
    if result is None:
        raise HTTPException(status_code=502, detail="Falha ao gerar mensagem")

    result["playbook_applied"] = bool(playbook)

    log_activity(
        db, lead, action=LeadActivityAction.MESSAGE_GENERATED,
        user_id=str(_user.id) if _user else None,
        detail=f"Mensagens geradas (canal: {body.channel})",
    )
    db.commit()

    return result


@router.post("/{lead_id}/enrich-contacts")
@limiter.limit("20/minute")
async def enrich_lead_contacts(
    request: Request,
    lead_id: str,
    body: EnrichContactsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Enriquece decisores do lead com e-mail e LinkedIn (busca passiva).

    - Fonte primária de decisores: Receita Federal via CNPJ (se informado).
    - E-mail: Hunter.io (opcional) → heurística determinística.
    - LinkedIn: busca passiva em buscador → heurística de URL + validação HEAD.
    - Registra `CONTACT_ENRICHED` na trilha.
    """
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    from services.contact_enrichment_service import ContactEnrichmentService  # noqa: E402

    service = ContactEnrichmentService()
    contacts = await service.enrich_contacts(lead, db, cnpj=body.cnpj or None)
    db.commit()

    log_activity(
        db, lead, action=LeadActivityAction.CONTACT_ENRICHED,
        user_id=str(user.id) if user else None,
        detail=f"Decisores enriquecidos: {len(contacts)} contato(s) (e-mail/LinkedIn)",
    )
    db.commit()

    return {"contacts": contacts}


class AssociateLinkedInRequest(BaseModel):
    url: str


@router.get("/{lead_id}/linkedin-query")
def get_linkedin_queries(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Consultas sugeridas para achar o decisor no LinkedIn.

    Gera `"<empresa>" <papel> linkedin` a partir do nome da empresa (padrão
    ou `playbook.linkedin_queries` do template da campanha) e devolve um
    atalho de busca externa `site:linkedin.com/in` para abrir fora do app.
    """
    from src.services.linkedin_assist_service import build_linkedin_queries

    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    playbook = None
    if lead.campaign_id:
        from src.db.models import CampaignScoringTemplate
        campaign = db.query(Campaign).filter(Campaign.id == lead.campaign_id).first()
        if campaign and campaign.scoring_template_id:
            template = db.query(CampaignScoringTemplate).filter(
                CampaignScoringTemplate.id == campaign.scoring_template_id,
            ).first()
            if template:
                playbook = template.playbook or {}

    company = lead.company_name or lead.name or ""
    queries = build_linkedin_queries(company, playbook)
    search_url = "https://www.google.com/search?q=" + quote(
        f'site:linkedin.com/in "{company}"'
    )
    return {"queries": queries, "search_url": search_url}


@router.patch("/{lead_id}/contacts/{contact_id}/linkedin")
@limiter.limit("20/minute")
async def associate_contact_linkedin(
    request: Request,
    lead_id: str,
    contact_id: str,
    body: AssociateLinkedInRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Associa manualmente um perfil LinkedIn a um decisor.

    Valida o formato da URL e a existência passiva no índice de busca; grava
    `linkedin_source="manual:<user_id>"` com confidence 90 (validado) ou 60
    (candidato para revisão) e registra `LINKEDIN_ASSOCIATED` na trilha.
    """
    from src.services.linkedin_assist_service import (
        LinkedInAssistService,
        extract_linkedin_username,
    )

    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    contact = db.query(Contact).filter(
        Contact.id == contact_id,
        Contact.lead_id == lead.id,
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contato não encontrado")

    username = extract_linkedin_username(body.url)
    if not username:
        raise HTTPException(
            status_code=422,
            detail="URL do LinkedIn inválida — use linkedin.com/in/<perfil>",
        )

    service = LinkedInAssistService()
    validated = await service.profile_exists(username)
    service.associate(
        db,
        lead,
        contact,
        username,
        user_id=str(user.id) if user else "auto",
        validated=validated,
    )
    db.commit()
    return _contact_to_dict(contact)


class RegisterConversionRequest(BaseModel):
    service_sold: Optional[str] = None
    contract_value: Optional[float] = None
    notes: Optional[str] = None


class UpdateNegotiationRequest(BaseModel):
    """Funil interno de negociação (RD/ORÇAMENTO/RP).

    `negotiation_stage`: RD | ORÇAMENTO | RP (progride da demonstração à
    proposta); `contract_outcome`: APROVADO | REPROVADO | EM_ANALISE. `null`
    limpa o campo.
    """
    negotiation_stage: Optional[NegotiationStage] = None
    contract_outcome: Optional[ContractOutcome] = None


class RegisterPostSaleRequest(BaseModel):
    """Pós-venda: canal do 1º contato pós-cliente e lembrete.

    `channel` é o canal do contato (WhatsApp/E-mail). `subject`/`content`, se
    informados, criam um lembrete de acompanhamento pós-cliente que roda pelo
    mesmo motor da cadência (`FollowUp.step=POST_SALE`), enviável manualmente ou
    (com `auto_send_email` da org) pelo scheduler quando vence.
    """
    channel: PostSaleChannel = PostSaleChannel.EMAIL
    subject: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None


@router.post("/{lead_id}/conversion")
def register_conversion(
    lead_id: str,
    body: RegisterConversionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Registra a conversão (venda fechada) de um lead.

    Cria um registro em `conversions` (base do dashboard
    "taxa de acerto do score" e das métricas de receita) e grava a action
    `CONVERTED` na trilha do lead. `time_to_close_days` é derivado de
    `created_at` do lead.
    """
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")
    if body.contract_value is not None and body.contract_value < 0:
        raise HTTPException(status_code=400, detail="contract_value não pode ser negativo")

    from datetime import datetime, timezone
    days_to_close = None
    if lead.created_at:
        days_to_close = max(
            0, (datetime.now(timezone.utc) - lead.created_at).days,
        )

    conversion = Conversion(
        lead_id=lead.id,
        service_sold=body.service_sold,
        contract_value=body.contract_value,
        notes=body.notes,
        time_to_close_days=days_to_close,
        user_id=user.id,
        assigned_to_id=lead.assigned_to_id,
    )
    db.add(conversion)

    # Contrato fechado ⇒ resultado final APROVADO.
    lead.contract_outcome = ContractOutcome.APROVADO
    lead.outcome_date = conversion.converted_at or datetime.now(timezone.utc)

    detail_parts = ["Conversão registrada"]
    if body.service_sold:
        detail_parts.append(body.service_sold)
    if body.contract_value is not None:
        detail_parts.append(f"R$ {body.contract_value:,.2f}")
    log_activity(
        db, lead, action=LeadActivityAction.CONVERTED,
        user_id=str(user.id) if user else None,
        detail=" — ".join(detail_parts),
    )
    db.commit()
    db.refresh(conversion)

    from src.services.webhook_outbound_service import enqueue_webhook
    enqueue_webhook(
        background_tasks, db, lead.organization_id,
        event="conversion.created",
        data={
            "conversion_id": str(conversion.id),
            "lead_id": str(lead.id),
            "company_name": lead.company_name,
            "service_sold": conversion.service_sold,
            "contract_value": float(conversion.contract_value) if conversion.contract_value is not None else None,
            "converted_at": conversion.converted_at.isoformat() if conversion.converted_at else None,
            "converted_by": str(user.id) if user else None,
        },
    )

    return {
        "id": str(conversion.id),
        "lead_id": str(conversion.lead_id),
        "service_sold": conversion.service_sold,
        "contract_value": float(conversion.contract_value) if conversion.contract_value is not None else None,
        "time_to_close_days": conversion.time_to_close_days,
        "converted_at": conversion.converted_at.isoformat() if conversion.converted_at else None,
    }


@router.patch("/{lead_id}/negotiation")
def update_negotiation(
    lead_id: str,
    body: UpdateNegotiationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Registra o funil interno de negociação.

    Só faz sentido quando o lead está na fase comercial (RESPONDIDO em diante
    até PROPOSTA_ENVIADA). `negotiation_stage` e `contract_outcome` podem ser
    alterados/limpados aqui; `outcome_date` grava o momento da última marcação.
    """
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")
    if lead.status not in NEGOTIATION_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=("Negociação só pode ser registrada em "
                    "RESPONDIDO/REUNIAO_MARCADA/REUNIAO_FEITA/PROPOSTA_ENVIADA"),
        )

    from datetime import datetime, timezone
    changed = False
    if body.negotiation_stage is not None:
        lead.negotiation_stage = body.negotiation_stage
        changed = True
    if body.contract_outcome is not None:
        lead.contract_outcome = body.contract_outcome
        changed = True
    if changed:
        lead.outcome_date = datetime.now(timezone.utc)
        parts = []
        if lead.negotiation_stage:
            parts.append(f"Etapa: {lead.negotiation_stage.value}")
        if lead.contract_outcome:
            parts.append(f"Contrato: {lead.contract_outcome.value}")
        log_activity(
            db, lead, action=LeadActivityAction.NEGOTIATION_UPDATED,
            user_id=str(user.id) if user else None,
            detail="Negociação atualizada — " + "; ".join(parts) if parts else "Negociação atualizada",
        )
    db.commit()
    db.refresh(lead)

    return {
        "id": str(lead.id),
        "negotiation_stage": lead.negotiation_stage.value if lead.negotiation_stage else None,
        "contract_outcome": lead.contract_outcome.value if lead.contract_outcome else None,
        "outcome_date": lead.outcome_date.isoformat() if lead.outcome_date else None,
        "status": lead.status.value if lead.status else None,
    }


@router.post("/{lead_id}/post-sale")
def register_post_sale(
    lead_id: str,
    body: RegisterPostSaleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Registra o 1º contato de pós-venda.

    Só faz sentido para leads já convertidos (há `Conversion`). Grava a data e o
    canal, registra a action `POST_SALE` na trilha e agenda um lembrete de
    acompanhamento pós-cliente reutilizando o motor da cadência (FollowUp).
    """
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    has_conversion = db.query(Conversion.id).filter(Conversion.lead_id == lead.id).first()
    if not has_conversion:
        raise HTTPException(status_code=400, detail="Pós-venda só para leads convertidos")

    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    lead.post_sale_contacted_at = now
    lead.post_sale_channel = body.channel
    log_activity(
        db, lead, action=LeadActivityAction.POST_SALE,
        user_id=str(user.id) if user else None,
        detail=f"Pós-venda registrado — {body.channel.value}",
    )

    # Lembrete pós-cliente (mesmo motor da cadência), somente se houver
    # conteúdo — um lembrete sem texto seria auto-skipado pela `send_step`.
    if body.content:
        db.add(FollowUp(
            lead_id=lead.id,
            step=FollowUpStep.POST_SALE,
            channel=body.channel,
            subject=body.subject,
            content=body.content,
            scheduled_at=now + timedelta(days=FollowUpStep.POST_SALE.day_offset),
            status=FollowUpStatus.PENDING,
        ))

    db.commit()
    db.refresh(lead)
    return {
        "id": str(lead.id),
        "post_sale_contacted_at": lead.post_sale_contacted_at.isoformat() if lead.post_sale_contacted_at else None,
        "post_sale_channel": lead.post_sale_channel.value if lead.post_sale_channel else None,
        "status": lead.status.value if lead.status else None,
    }


def _build_lead_dict(lead: Lead, db: Session) -> dict:
    contacts = (
        db.query(Contact)
        .filter(Contact.lead_id == lead.id)
        .order_by(Contact.is_primary.desc())
        .all()
    )
    return {
        "company_name": lead.company_name,
        "category": lead.category,
        "city": lead.city,
        "state": lead.state,
        "website": lead.website,
        "instagram_url": lead.instagram_url,
        "evidence": lead.evidence,
        "primary_need": lead.primary_need,
        "pitch_angle": lead.pitch_angle,
        "qualification_reason": lead.qualification_reason,
        "contacts": [_contact_to_dict(c) for c in contacts],
        "email": lead.email,
    }


def _follow_up_dict(fu: FollowUp, db: Session, lead: Optional[Lead] = None,
                     _tracking_cache: Optional[dict] = None,
                     _recipients_cache: Optional[list] = None) -> dict:
    # Tracking 4.2: abertura/clique vêm do `Message` ligado pelo token.
    opened_at = clicked_at = None
    if fu.tracking_token:
        msg = None
        if _tracking_cache is not None and fu.tracking_token in _tracking_cache:
            msg = _tracking_cache[fu.tracking_token]
        else:
            msg = (
                db.query(Message)
                .filter(Message.tracking_token == fu.tracking_token)
                .first()
            )
            if _tracking_cache is not None:
                _tracking_cache[fu.tracking_token] = msg
        if msg:
            opened_at = msg.opened_at
            clicked_at = msg.clicked_at
    # Roteamento multi-decisor: etapa pendente mostra para quem vai sair.
    recipient = fu.recipient
    if not recipient and lead and fu.status == FollowUpStatus.PENDING and fu.content:
        from src.services.cadence_service import _planned_recipient, _recipients_so_far

        sent_to = _recipients_cache if _recipients_cache is not None else _recipients_so_far(db, str(lead.id))
        recipient = _planned_recipient(
            lead,
            step=fu.step,
            sent_to=sent_to,
        )
    return {
        "id": str(fu.id),
        "step": fu.step.value,
        "label": fu.step.label,
        "channel": fu.channel.value if fu.channel else None,
        "subject": fu.subject,
        "content": fu.content,
        "scheduled_at": fu.scheduled_at.isoformat() if fu.scheduled_at else None,
        "sent_at": fu.sent_at.isoformat() if fu.sent_at else None,
        "status": fu.status.value if fu.status else None,
        "attempts": fu.attempts or 0,
        "opened_at": opened_at.isoformat() if opened_at else None,
        "clicked_at": clicked_at.isoformat() if clicked_at else None,
        "variant": fu.variant,
        "recipient": recipient,
    }


@router.get("/{lead_id}/cadence")
def get_lead_cadence(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Lista as etapas da cadência (dia 0/3/7/14) de um lead."""
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    fups = (
        db.query(FollowUp)
        .filter(FollowUp.lead_id == lead.id)
        .order_by(FollowUp.scheduled_at.asc())
        .all()
    )
    # Batch prefetch de tracking tokens (M-P1) e recipients (P1-1):
    # evita N+1 queries no loop.
    tracking_tokens = [fu.tracking_token for fu in fups if fu.tracking_token]
    tracking_cache: dict = {}
    if tracking_tokens:
        messages = (
            db.query(Message)
            .filter(Message.tracking_token.in_(tracking_tokens))
            .all()
        )
        tracking_cache = {m.tracking_token: m for m in messages}

    # Pre-compute recipients_so_far para todos os follow_ups de uma vez.
    from src.services.cadence_service import _recipients_so_far
    recipients_cache = _recipients_so_far(db, str(lead.id)) if fups else []

    return {
        "lead_id": str(lead.id),
        "opt_out": bool(lead.opt_out),
        "organization_auto_send": bool(
            _org.auto_send_email if _org else False
        ),
        "follow_ups": [
            _follow_up_dict(f, db, lead=lead, _tracking_cache=tracking_cache,
                           _recipients_cache=recipients_cache)
            for f in fups
        ],
    }


@router.post("/{lead_id}/cadence/start")
async def start_lead_cadence(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Gera e agenda a cadência (dia 0/3/7/14) de um lead.

    Gera a sequência via OutreachService (com playbook da vertical) e cria as
    etapas em `follow_ups`. Envio efetivo depende do modo da org: humano
    (default) ou automático (`auto_send_email`).
    """
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")
    if lead.opt_out:
        raise HTTPException(status_code=400, detail="Lead com opt-out — não gere cadência")

    from services.provider_client import quota_ok
    if not quota_ok(db, str(_org.id), "GROQ_API_KEY"):
        raise HTTPException(status_code=429, detail="Cota diária de IA esgotada — tente amanhã.")

    campaign = (
        db.query(Campaign).filter(Campaign.id == lead.campaign_id).first()
        if lead.campaign_id
        else None
    )
    context_service = campaign.target_service if campaign else None
    context_segment = campaign.target_segment if campaign else None

    from services.secret_service import SecretService
    from services.outreach_service import OutreachService
    from services.template_router import get_playbook_for_campaign, route_scoring_template
    from src.services.cadence_service import schedule_cadence, _normalize_cadence_days, DEFAULT_CADENCE_DAYS

    keys = await SecretService.resolve_all(db, str(_org.id))
    groq = keys.get("GROQ_API_KEY")

    playbook = await get_playbook_for_campaign(
        db,
        target_service=context_service or "",
        target_segment=context_segment or "",
        explicit_template_id=str(campaign.scoring_template_id) if campaign and campaign.scoring_template_id else None,
        api_key=groq,
        organization_id=str(_org.id),
    )

    # Calendário do acompanhamento vem do template da campanha (pode ser
    # diferente do padrão 0/3/7/14 para ciclos industriais longos).
    template_schedule = None
    if campaign:
        try:
            route_result = await route_scoring_template(
                db,
                target_service=campaign.target_service or "",
                target_segment=campaign.target_segment or "",
                explicit_template_id=str(campaign.scoring_template_id) if campaign.scoring_template_id else None,
                api_key=groq,
                organization_id=str(_org.id),
            )
            tmpl = route_result.get("template") or {}
            declared = tmpl.get("cadence_schedule")
            if declared and len(declared) == 4:
                template_schedule = declared
        except Exception:  # noqa: BLE001 — nunca impede de gerar a cadência
            logger.warning("Falha ao resolver calendário do template para cadência", exc_info=True)
    day_offsets = _normalize_cadence_days(template_schedule)

    lead_dict = _build_lead_dict(lead, db)
    result = await OutreachService(api_key=groq).generate_sequence(
        lead_dict, context_service or "", context_segment or "", playbook,
        db=db,
        organization_id=str(_org.id),
    )
    if result is None:
        raise HTTPException(status_code=502, detail="Falha ao gerar mensagens da cadência")

    follow_ups = schedule_cadence(
        db, lead, result,
        organization=_org,
        user_id=str(_user.id) if _user else None,
        day_offsets=day_offsets,
    )

    # NENHUM envio automático aqui. O scheduler (`run_due`) envia
    # cada etapa quando `scheduled_at` vence apenas para orgs com
    # `auto_send_email`. Enviar o ciclo inteiro de uma vez queimava a
    # entregabilidade.

    return {
        "lead_id": str(lead.id),
        "playbook_applied": bool(playbook),
        "auto_send": bool(_org.auto_send_email),
        "schedule": day_offsets,
        "follow_ups": [_follow_up_dict(f, db) for f in follow_ups],
    }


class UpdateCadenceStepRequest(BaseModel):
    """Atualiza uma etapa da cadência (escolha de variante A/B + conteúdo)."""
    variant: Optional[str] = Field(None, max_length=32)
    subject: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None


@router.patch("/{lead_id}/cadence/step/{step}")
def update_cadence_step(
    lead_id: str,
    step: str,
    body: UpdateCadenceStepRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Atualiza uma etapa da cadência (escolha de variante A/B ou edição
    manual). Não dispara envio — o consultor usa `/cadence/send/{step}`.

    `variant` é a etiqueta (ex.: "A"/"B") marcada após o consultor escolher
    qual das alternativas geradas pelo endpoint `/generate-messages` será
    usada. `subject`/`content` permitem edição inline antes do envio.
    """
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    try:
        fstep = FollowUpStep(step)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Etapa inválida: {step}")

    fu = db.query(FollowUp).filter(
        FollowUp.lead_id == lead.id,
        FollowUp.step == fstep,
    ).order_by(FollowUp.created_at.desc()).first()
    if not fu:
        raise HTTPException(status_code=404, detail="Etapa de cadência não encontrada")
    if fu.status == FollowUpStatus.SENT:
        raise HTTPException(
            status_code=400,
            detail="Etapa já enviada — não é possível alterar variante/conteúdo",
        )

    # Salvar versão antes de editar (se houver mudança de conteúdo)
    content_changed = body.content is not None and body.content != fu.content
    subject_changed = body.subject is not None and body.subject != fu.subject
    variant_changed = body.variant is not None and body.variant != fu.variant

    if content_changed or subject_changed or variant_changed:
        from src.db.models import FollowUpVersion
        # Calcular próximo número de versão
        last_version = db.query(FollowUpVersion).filter(
            FollowUpVersion.follow_up_id == fu.id,
        ).order_by(FollowUpVersion.version_number.desc()).first()
        next_version = (last_version.version_number + 1) if last_version else 1

        version = FollowUpVersion(
            follow_up_id=fu.id,
            version_number=next_version,
            subject=fu.subject,
            content=fu.content,
            variant=fu.variant,
            edited_by_id=_user.id if _user else None,
        )
        db.add(version)

    if body.variant is not None:
        fu.variant = body.variant.strip().upper()[:32] or None
    if body.subject is not None:
        fu.subject = body.subject.strip()[:255] or None
    if body.content is not None:
        fu.content = body.content

    db.commit()
    db.refresh(fu)
    return _follow_up_dict(fu, db)


@router.get("/{lead_id}/cadence/step/{step}/versions")
def get_cadence_step_versions(
    lead_id: str,
    step: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Retorna histórico de versões de uma etapa da cadência.

    Lista todas as versões salvas antes de edições, ordenadas da mais
    recente para a mais antiga. Útil para comparar mudanças de copywriting
    e reverter se necessário.
    """
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    try:
        fstep = FollowUpStep(step)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Etapa inválida: {step}")

    fu = db.query(FollowUp).filter(
        FollowUp.lead_id == lead.id,
        FollowUp.step == fstep,
    ).order_by(FollowUp.created_at.desc()).first()
    if not fu:
        raise HTTPException(status_code=404, detail="Etapa de cadência não encontrada")

    from src.db.models import FollowUpVersion, User as UserModel

    versions = db.query(FollowUpVersion).filter(
        FollowUpVersion.follow_up_id == fu.id,
    ).order_by(FollowUpVersion.version_number.desc()).all()

    # Batch prefetch de editores (P1-2): evita N+1 queries no loop.
    editor_ids = {v.edited_by_id for v in versions if v.edited_by_id}
    editors = {}
    if editor_ids:
        editor_rows = db.query(UserModel).filter(UserModel.id.in_(editor_ids)).all()
        editors = {str(u.id): u.name for u in editor_rows}

    result = []
    for v in versions:
        editor = editors.get(str(v.edited_by_id)) if v.edited_by_id else None
        result.append({
            "id": str(v.id),
            "version_number": v.version_number,
            "subject": v.subject,
            "content": v.content,
            "variant": v.variant,
            "edited_by": editor,
            "edit_reason": v.edit_reason,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        })

    return {"versions": result, "current": {
        "subject": fu.subject,
        "content": fu.content,
        "variant": fu.variant,
    }}


@router.post("/{lead_id}/cadence/send/{step}")
def send_cadence_step(
    lead_id: str,
    step: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Envia manualmente uma etapa da cadência (humano-no-loop).

    O consultor envia pela UI (abertura/follow-up 1/2/encerramento) quando
    estiver pronto. O envio automático só ocorre se a org opt-in.
    """
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    try:
        fstep = FollowUpStep(step)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Etapa inválida: {step}")

    fu = db.query(FollowUp).filter(
        FollowUp.lead_id == lead.id,
        FollowUp.step == fstep,
    ).order_by(FollowUp.created_at.desc()).first()
    if not fu:
        raise HTTPException(status_code=404, detail="Etapa de cadência não encontrada")

    from src.services.cadence_service import send_step
    ok = send_step(db, fu, user_id=str(_user.id) if _user else None)
    if not ok:
        raise HTTPException(status_code=400, detail="Etapa não pôde ser enviada (opt-out ou sem conteúdo)")

    return _follow_up_dict(fu, db)


@router.post("/{lead_id}/opt-out")
def opt_out_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Registra opt-out de um lead: cancela cadência e impede novos envios."""
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    from src.services.cadence_service import mark_opt_out
    mark_opt_out(db, lead)
    return {"lead_id": str(lead.id), "opt_out": True}


def _format_whatsapp_url(phone: Optional[str], text: Optional[str] = None) -> tuple[Optional[str], Optional[str], bool]:
    if not phone:
        return None, None, False
    digits = "".join(filter(str.isdigit, phone))
    if len(digits) < 10 or len(digits) > 13:
        return None, phone, False
    with_country = digits if (len(digits) == 12 or len(digits) == 13) else f"55{digits}"
    is_mobile = len(digits) == 11 or (len(digits) == 13 and digits.startswith("55"))
    from urllib.parse import quote
    base = f"https://wa.me/{with_country}"
    url = f"{base}?text={quote(text)}" if text else base
    return url, with_country, is_mobile


@router.post("/{lead_id}/whatsapp-click")
def record_whatsapp_click(
    lead_id: str,
    body: Optional[RecordWhatsAppClickRequest] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Registra acionamento do WhatsApp e retorna link wa.me formatado."""
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.organization_id == _org.id,
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    if not _can_access_lead(member, lead):
        raise HTTPException(status_code=403, detail="Acesso negado a este lead")

    phone = lead.whatsapp or lead.phone
    text = body.message_text if body else None
    url, formatted_number, is_valid = _format_whatsapp_url(phone, text)

    if not url:
        raise HTTPException(status_code=400, detail="Lead não possui número de telefone/WhatsApp válido")

    from datetime import datetime, timezone
    lead.last_contacted_at = datetime.now(timezone.utc)

    log_activity(
        db, lead,
        action=LeadActivityAction.WHATSAPP_SENT,
        user_id=str(user.id),
        detail=f"WhatsApp acionado ({formatted_number})",
    )
    db.commit()
    db.refresh(lead)

    return {
        "whatsapp_url": url,
        "phone": formatted_number,
        "is_valid": is_valid,
        "last_contacted_at": lead.last_contacted_at.isoformat(),
    }
