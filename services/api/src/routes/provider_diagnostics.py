"""Teste manual das conexões externas do workspace."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.dependencies import get_user_organization, require_org_admin
from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember
from src.services.provider_diagnostics_service import ProviderDiagnosticsService

router = APIRouter(prefix="/orgs", tags=["orgs"])


class ProviderDiagnosticsRequest(BaseModel):
    providers: list[str] | None = Field(default=None, max_length=3)


@router.post("/{org_id}/provider-diagnostics")
async def provider_diagnostics(
    org_id: str,
    body: ProviderDiagnosticsRequest,
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_org_admin),
):
    """Valida as conexões configuradas sem revelar segredos.

    É uma ação explícita de administrador: nenhuma chamada externa ocorre em
    background apenas porque uma chave está configurada.
    """
    if str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")
    try:
        return await ProviderDiagnosticsService().diagnose(db, org_id, body.providers)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
