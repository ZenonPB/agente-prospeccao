from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import os
import sys
import logging

logger = logging.getLogger(__name__)

from src.db.dependencies import get_db
from src.db.models import Lead, LeadStatus, Enrichment, Contact, CompanyRecord, ContactRole, Campaign, User, Organization, OrganizationMember, LeadActivity, LeadActivityAction, Conversion, FollowUp, FollowUpStatus, FollowUpStep
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

router = APIRouter(prefix="/leads", tags=["leads"])


class UpdateLeadStatusRequest(BaseModel):
    status: LeadStatus


class UpdateLeadRequest(BaseModel):
    """Campos de trabalho do consultor (item 4.4 da auditoria)."""
    notes: Optional[str] = None
    whatsapp: Optional[str] = None
    next_action_at: Optional[str] = None  # ISO datetime (tz-aware) ou null
    last_contacted_at: Optional[str] = None


class EnrichContactsRequest(BaseModel):
    cnpj: str


class GenerateMessagesRequest(BaseModel):
    channel: str = "EMAIL"  # EMAIL | WHATSAPP — afeta foco de retorno hoje
    force_regenerate: bool = False


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
        "linkedin_url": c.linkedin_url,
        "linkedin_confidence": c.linkedin_confidence,
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
    }


def _lead_detail(lead: Lead, enrichment: Optional[Enrichment]) -> dict:
    """Detalhe do lead com evidence/score_factors estruturados."""
    summary = _lead_summary(lead)
    summary.update({
        "notes": lead.notes,
        "next_action_at": lead.next_action_at.isoformat() if lead.next_action_at else None,
        "last_contacted_at": lead.last_contacted_at.isoformat() if lead.last_contacted_at else None,
        "address": lead.address,
        "score_factors": lead.score_factors,
        "evidence": lead.evidence,
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
            "raw_technical_data": enrichment.raw_technical_data,
            "created_at": enrichment.created_at.isoformat() if enrichment.created_at else None,
            "updated_at": enrichment.updated_at.isoformat() if enrichment.updated_at else None,
        } if enrichment else None,
    })
    return summary


def _can_access_lead(member: OrganizationMember, lead: Lead) -> bool:
    """True se o membro pode ver/editar o lead (regra 2.1.3).

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
        .options(joinedload(Lead.assigned_to))
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


@router.patch("/{lead_id}/status")
def update_lead_status(
    lead_id: str,
    body: UpdateLeadStatusRequest,
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
    log_status_change(
        db, lead, user_id=str(user.id), status_to=body.status,
        status_from=previous,
        detail=f"{previous.value if previous else '?'} → {body.status.value}",
    )
    # Item 3.6: grava também a action comercial correspondente (ex.: REUNIAO_MARCADA
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

    return {
        "id": str(lead.id),
        "company_name": lead.company_name,
        "status": lead.status.value if lead.status else None,
    }


@router.delete("/{lead_id}")
def delete_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
    user: User = Depends(get_current_user),
):
    """Exclui um lead e seus dados relacionados (direito ao apagamento — LGPD).

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
    último contato (item 4.4). Requer acesso ao lead (regra 2.1.3)."""
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

    db.commit()
    db.refresh(lead)
    return _lead_detail(lead, db.query(Enrichment).filter(Enrichment.lead_id == lead.id).first())


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
    - CONSULTOR pode se auto-atribuir um lead não atribuído (regra 2.1.3);
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
        member = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == _org.id,
            OrganizationMember.user_id == new_assignee.id,
        ).first()
        if not member:
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


@router.get("/{lead_id}")
def get_lead(
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

    return _lead_detail(lead, enrichment)


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
    )

    lead_dict = _build_lead_dict(lead, db)
    result = await OutreachService(api_key=groq).generate_sequence(
        lead_dict, context_service or "", context_segment or "", playbook,
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


class RegisterConversionRequest(BaseModel):
    service_sold: Optional[str] = None
    contract_value: Optional[float] = None
    notes: Optional[str] = None


@router.post("/{lead_id}/conversion")
def register_conversion(
    lead_id: str,
    body: RegisterConversionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Registra a conversão (venda fechada) de um lead.

    Item 3.6.1: cria um registro em `conversions` (base do dashboard
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

    return {
        "id": str(conversion.id),
        "lead_id": str(conversion.lead_id),
        "service_sold": conversion.service_sold,
        "contract_value": float(conversion.contract_value) if conversion.contract_value is not None else None,
        "time_to_close_days": conversion.time_to_close_days,
        "converted_at": conversion.converted_at.isoformat() if conversion.converted_at else None,
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
        "evidence": lead.evidence,
        "primary_need": lead.primary_need,
        "pitch_angle": lead.pitch_angle,
        "qualification_reason": lead.qualification_reason,
        "contacts": [_contact_to_dict(c) for c in contacts],
        "email": lead.email,
    }


def _follow_up_dict(fu: FollowUp) -> dict:
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
    }


@router.get("/{lead_id}/cadence")
def get_lead_cadence(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Lista as etapas da cadência (dia 0/3/7/14) de um lead (item 3.7)."""
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
    return {
        "lead_id": str(lead.id),
        "opt_out": bool(lead.opt_out),
        "organization_auto_send": bool(
            _org.auto_send_email if _org else False
        ),
        "follow_ups": [_follow_up_dict(f) for f in fups],
    }


@router.post("/{lead_id}/cadence/start")
async def start_lead_cadence(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Gera e agenda a cadência (dia 0/3/7/14) de um lead (item 3.7).

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

    campaign = (
        db.query(Campaign).filter(Campaign.id == lead.campaign_id).first()
        if lead.campaign_id
        else None
    )
    context_service = campaign.target_service if campaign else None
    context_segment = campaign.target_segment if campaign else None

    from services.secret_service import SecretService
    from services.outreach_service import OutreachService
    from services.template_router import get_playbook_for_campaign

    keys = await SecretService.resolve_all(db, str(_org.id))
    groq = keys.get("GROQ_API_KEY")

    playbook = await get_playbook_for_campaign(
        db,
        target_service=context_service or "",
        target_segment=context_segment or "",
        explicit_template_id=str(campaign.scoring_template_id) if campaign and campaign.scoring_template_id else None,
        api_key=groq,
    )

    lead_dict = _build_lead_dict(lead, db)
    result = await OutreachService(api_key=groq).generate_sequence(
        lead_dict, context_service or "", context_segment or "", playbook,
    )
    if result is None:
        raise HTTPException(status_code=502, detail="Falha ao gerar mensagens da cadência")

    from src.services.cadence_service import schedule_cadence
    follow_ups = schedule_cadence(
        db, lead, result,
        organization=_org,
        user_id=str(_user.id) if _user else None,
    )

    # Item 3.7: NENHUM envio automático aqui. O scheduler (`run_due`) envia
    # cada etapa quando `scheduled_at` vence (dia 0/3/7/14) apenas para orgs
    # com `auto_send_email`. Enviar o ciclo inteiro de uma vez queimava a
    # entregabilidade (bug fix/go-live 2.3).

    return {
        "lead_id": str(lead.id),
        "playbook_applied": bool(playbook),
        "auto_send": bool(_org.auto_send_email),
        "follow_ups": [_follow_up_dict(f) for f in follow_ups],
    }


@router.post("/{lead_id}/cadence/send/{step}")
def send_cadence_step(
    lead_id: str,
    step: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Envia manualmente uma etapa da cadência (humano-no-loop, item 3.7).

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

    return _follow_up_dict(fu)


@router.post("/{lead_id}/opt-out")
def opt_out_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Registra opt-out LGPD de um lead: cancela cadência e impede novos envios."""
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
