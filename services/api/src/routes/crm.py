"""Rotas do CRM e integrações comerciais."""
import io
import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
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
    aba_name: str = Form(default=""),
    criar_aba: bool = Form(default=False),
    member=Depends(get_user_membership),
    db=Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .xlsx")
    max_upload_bytes = 10 * 1024 * 1024
    content = await file.read()
    if len(content) > max_upload_bytes:
        raise HTTPException(status_code=413, detail="Arquivo excede 10 MB")
    if content[:4] != b"PK\x03\x04":
        raise HTTPException(status_code=400, detail="Arquivo não é um .xlsx válido")

    from src.db.models import Contact, FollowUp, Lead

    user = member.user
    aba = aba_name.strip() if aba_name and aba_name.strip() else _resolve_aba_consultor(getattr(user, "name", None) or "Zenon")
    leads = db.query(Lead).filter(Lead.organization_id == member.organization_id, Lead.assigned_to_id == member.user_id).all()
    lead_ids = [lead.id for lead in leads]
    contacts_by_lead: dict = {}
    followups_by_lead: dict = {}
    if lead_ids:
        for contact in db.query(Contact).filter(Contact.lead_id.in_(lead_ids)).all():
            contacts_by_lead.setdefault(str(contact.lead_id), []).append(contact)
        for follow_up in db.query(FollowUp).filter(FollowUp.lead_id.in_(lead_ids)).all():
            followups_by_lead.setdefault(str(follow_up.lead_id), {})[follow_up.step] = follow_up.scheduled_at

    suffix = os.path.splitext(file.filename or "crm.xlsx")[1]
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
        try:
            result = complementa_planilha(tmp_path, aba, leads, contacts_by_lead, followups_by_lead, criar_aba_se_ausente=criar_aba)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        with open(tmp_path, "rb") as source:
            output_content = source.read()
        filename = f"Planilha_aprimorada_{aba}.xlsx"
        return StreamingResponse(
            io.BytesIO(output_content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}", "X-CRM-Inseridos": str(result["inseridos"]), "X-CRM-Duplicados": str(result["duplicados"])},
        )
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


from src.routes.crm_sync import router as crm_sync_router  # noqa: E402
from src.routes.commercial_intelligence import router as intelligence_router  # noqa: E402
from src.routes.prospect_lists import router as prospect_lists_router  # noqa: E402
from src.routes.sales_operating import router as sales_operating_router  # noqa: E402
from src.routes.sales_operating_listing import router as sales_operating_listing_router  # noqa: E402

router.include_router(crm_sync_router)
router.include_router(intelligence_router)
router.include_router(prospect_lists_router)
router.include_router(sales_operating_router)
router.include_router(sales_operating_listing_router)
