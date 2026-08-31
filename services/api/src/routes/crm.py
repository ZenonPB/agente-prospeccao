"""Rotas do CRM — preenchimento da planilha a partir dos leads do sistema.

- POST /api/crm/spreadsheet/atualizar — recebe o arquivo .xlsx, lista os leads
  do consultor autenticado, preenche a aba do consultor e devolve o arquivo
  atualizado (StreamingResponse).
"""
import io
import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from src.auth.dependencies import get_user_membership
from src.db.dependencies import get_db
from src.services.crm_spreadsheet_service import complementa_planilha

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crm", tags=["crm"])


def _resolve_aba_consultor(name: str) -> str:
    if not name:
        return "Zenon"
    return name.strip()


@router.post("/spreadsheet/atualizar")
async def atualizar_planilha(
    file: UploadFile = File(...),
    member=Depends(get_user_membership),
    db=Depends(get_db),
):
    """Lê o .xlsx enviado, preenche a aba do consultor com os leads atribuídos a ele
    e devolve o arquivo atualizado."""
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .xlsx")

    from src.db.models import Contact, FollowUp, Lead

    user = member.user
    aba = _resolve_aba_consultor(getattr(user, "name", None) or "Zenon")

    leads = (
        db.query(Lead)
        .filter(Lead.organization_id == member.organization_id, Lead.assigned_to_id == member.user_id)
        .all()
    )
    lead_ids = [lead.id for lead in leads]

    contacts_by_lead: dict = {}
    followups_by_lead: dict = {}
    if lead_ids:
        for c in db.query(Contact).filter(Contact.lead_id.in_(lead_ids)).all():
            contacts_by_lead.setdefault(str(c.lead_id), []).append(c)
        for f in db.query(FollowUp).filter(FollowUp.lead_id.in_(lead_ids)).all():
            followups_by_lead.setdefault(str(f.lead_id), {})[f.step] = f.scheduled_at

    suffix = os.path.splitext(file.filename or "crm.xlsx")[1]
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(await file.read())
        try:
            result = complementa_planilha(
                tmp_path, aba, leads, contacts_by_lead, followups_by_lead,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        with open(tmp_path, "rb") as f:
            content = f.read()

        filename = f"Planilha_aprimorada_{aba}.xlsx"
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-CRM-Inseridos": str(result["inseridos"]),
                "X-CRM-Duplicados": str(result["duplicados"]),
            },
        )
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
