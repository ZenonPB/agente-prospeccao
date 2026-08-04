from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import os
import sys

from src.db.dependencies import get_db
from src.db.models import Lead, LeadStatus, Enrichment, Contact, CompanyRecord, ContactRole, Campaign, User, Organization, OrganizationMember, LeadActivity, LeadActivityAction
from src.auth.dependencies import get_current_user, get_user_organization, get_user_membership
from src.services.lead_activity_service import log_activity, log_status_change
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
        "company_name": lead.company_name,
        "website": lead.website,
        "phone": lead.phone,
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

    total = query.count()
    leads = query.order_by(Lead.qualification_score.desc()).offset(offset).limit(limit).all()

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
    db.commit()
    db.refresh(lead)

    return {
        "id": str(lead.id),
        "company_name": lead.company_name,
        "status": lead.status.value if lead.status else None,
    }


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
async def generate_messages(
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

    contacts = (
        db.query(Contact)
        .filter(Contact.lead_id == lead.id)
        .order_by(Contact.is_primary.desc())
        .all()
    )

    lead_dict = {
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

    result = await OutreachService().generate_sequence(
        lead_dict, context_service or "", context_segment or ""
    )
    if result is None:
        raise HTTPException(status_code=502, detail="Falha ao gerar mensagem")

    log_activity(
        db, lead, action=LeadActivityAction.MESSAGE_GENERATED,
        user_id=str(_user.id) if _user else None,
        detail=f"Mensagens geradas (canal: {body.channel})",
    )
    db.commit()

    return result


@router.post("/{lead_id}/enrich-contacts")
async def enrich_lead_contacts(
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
