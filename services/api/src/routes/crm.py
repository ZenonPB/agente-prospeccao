"""Rotas do lançamento rápido de leads ("CRM Paste").

- POST /api/crm/extract       — IA extrai leads do texto livre (preview, sem inserir).
- POST /api/crm/batch-import  — insere os itens (pós-edição do preview) com dedupe.
- GET  /api/crm/export-xlsx   — exporta o CRM no formato da planilha (aba por consultor).
"""
import io
import logging
import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.auth.dependencies import get_current_user, get_user_membership
from src.db.dependencies import get_db
from src.middleware.rate_limit import limiter
from src.services.crm_service import extract_leads, insert_items, normalize_items

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crm", tags=["crm"])


class CrmExtractRequest(BaseModel):
    raw_text: str = Field(..., min_length=3, max_length=20000)


class CrmItem(BaseModel):
    """Um lead extraído/editado na tabela de preview."""
    lead: str = Field(..., min_length=1, max_length=255)
    empresa: str = Field(..., min_length=1, max_length=255)
    prospeccao: Optional[date] = None
    pitch_enviado: bool = False
    pitch_data: Optional[date] = None
    follow_up_1: Optional[date] = None
    follow_up_2: Optional[date] = None
    follow_up_3: Optional[date] = None
    respondeu: Optional[str] = None
    cargo: Optional[str] = None
    observacoes: Optional[str] = None


class CrmBatchImportRequest(BaseModel):
    """Itens já extraídos/editados (fluxo do preview) OU texto bruto."""
    items: Optional[List[CrmItem]] = None
    raw_text: Optional[str] = Field(None, max_length=20000)
    consultant_user_id: Optional[str] = None
    campaign_id: Optional[str] = None


@router.post("/extract")
@limiter.limit("10/minute")
async def extract_crm_leads(
    request: Request,
    body: CrmExtractRequest,
    member=Depends(get_user_membership),
):
    """Extrai leads do texto colado via Groq — só preview, não grava nada."""
    items = await extract_leads(body.raw_text)
    return {"items": items}


@router.post("/batch-import")
async def batch_import_crm_leads(
    body: CrmBatchImportRequest,
    member=Depends(get_user_membership),
    db=Depends(get_db),
):
    """Insere os leads no CRM (com dedupe por pessoa+empresa na organização)."""
    from src.db.models import Organization

    organization = member.organization
    if organization is None:
        organization = db.query(Organization).filter(Organization.id == member.organization_id).first()
    if organization is None:
        raise HTTPException(status_code=403, detail="Organização não encontrada")

    items: List[dict] = []
    if body.items:
        # Pós-edição do preview: normaliza de novo (datas, respondeu e
        # follow-ups default caso o usuário tenha apagado alguma célula).
        items = normalize_items([item.model_dump() for item in body.items])
    elif body.raw_text:
        items = await extract_leads(body.raw_text)
    else:
        raise HTTPException(status_code=422, detail="Informe `items` ou `raw_text`")

    if not items:
        return {"inserted": 0, "duplicates": 0, "errors": ["Nenhum lead reconhecido no texto."]}

    consultant_user_id = body.consultant_user_id
    if consultant_user_id is not None:
        try:
            uuid.UUID(consultant_user_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="consultant_user_id inválido")

    try:
        result = insert_items(
            db,
            organization,
            items,
            consultant_user_id=consultant_user_id,
            campaign_id=body.campaign_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result


# Colunas exatas da planilha de CRM (docs/Planilha_aprimorada.xlsx).
EXPORT_HEADERS = [
    "LEAD", "Empresa", "Prospecção", "PITCH ENVIADO", "PITCH",
    "1º Follow-up", "2º Follow-up", "3º Follow-up", "RESPONDEU?", "CARGO",
    "Observações lead", "Status", "DATA status", "ANOTAÇÕES", "CONTRATO FINAL",
    "DATA CONTATO PÓS-VENDA", "Follow-up", "PÓS VENDA POR:",
    "Link ou Telefone ou e-mail do Lead",
]


def _fmt_date(value) -> str:
    """Data no formato DD/MM/AAAA da planilha."""
    if value is None:
        return ""
    if hasattr(value, "date"):
        value = value.date()
    return value.strftime("%d/%m/%Y")


@router.get("/export-xlsx")
def export_crm_xlsx(
    consultant_user_id: Optional[str] = Query(None),
    member=Depends(get_user_membership),
    db=Depends(get_db),
):
    """Exporta o CRM da organização no formato da planilha original.

    Sem `consultant_user_id` exporta todos os leads da org; com o parâmetro,
    só os atribuídos ao consultor (equivale à aba dele na planilha).
    """
    from openpyxl import Workbook

    from src.db.models import (
        Contact, FollowUp, FollowUpStep, Lead, User,
    )

    consultant_name = None
    query = db.query(Lead).filter(Lead.organization_id == member.organization_id)
    if consultant_user_id:
        query = query.filter(Lead.assigned_to_id == consultant_user_id)
        consultant = db.query(User).filter(User.id == consultant_user_id).first()
        consultant_name = consultant.name if consultant else None

    leads = query.order_by(Lead.created_at.asc()).all()
    lead_ids = [lead.id for lead in leads]

    primary_contacts = {}
    followups_by_lead = {}
    if lead_ids:
        contacts = (
            db.query(Contact)
            .filter(Contact.lead_id.in_(lead_ids), Contact.is_primary.is_(True))
            .all()
        )
        primary_contacts = {c.lead_id: c for c in contacts}
        fups = db.query(FollowUp).filter(FollowUp.lead_id.in_(lead_ids)).all()
        for fup in fups:
            followups_by_lead.setdefault(fup.lead_id, {})[fup.step] = fup.scheduled_at

    def fup(lead_id, step: FollowUpStep):
        return _fmt_date(followups_by_lead.get(lead_id, {}).get(step))

    sheet_name = (consultant_name or "CRM")[:31]  # limite do Excel
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name or "CRM"
    sheet.append(EXPORT_HEADERS)

    for lead in leads:
        contact = primary_contacts.get(lead.id)
        contact_info = lead.website or lead.phone or lead.email or ""
        sheet.append([
            contact.name if contact else "",
            lead.company_name,
            _fmt_date(lead.assigned_at),
            "TRUE" if lead.last_contacted_at else "FALSE",
            _fmt_date(lead.last_contacted_at),
            fup(lead.id, FollowUpStep.FOLLOWUP_1),
            fup(lead.id, FollowUpStep.FOLLOWUP_2),
            fup(lead.id, FollowUpStep.CLOSING),
            "SIM" if lead.status and lead.status.value == "RESPONDIDO" else "NÃO",
            contact.role_label if contact else "",
            lead.notes or "",
            lead.negotiation_stage.value if lead.negotiation_stage else "",
            _fmt_date(lead.outcome_date),
            "",
            lead.contract_outcome.value if lead.contract_outcome else "",
            _fmt_date(lead.post_sale_contacted_at),
            _fmt_date(lead.next_action_at),
            lead.post_sale_channel.value if lead.post_sale_channel else "",
            contact_info,
        ])

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    filename = f"crm_{(consultant_name or 'todos').strip().replace(' ', '_').lower()}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
