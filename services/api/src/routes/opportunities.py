"""Rotas de leitura agregada para oportunidades comerciais."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.dependencies import get_user_membership, get_user_organization
from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember
from src.services.opportunity_360_service import Opportunity360Service

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.get("/{opportunity_id}/360")
def get_opportunity_360(
    opportunity_id: str,
    db: Session = Depends(get_db),
    organization: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Retorna a visão comercial consolidada da oportunidade no workspace ativo."""
    payload = Opportunity360Service(
        db,
        organization_id=organization.id,
        member=member,
    ).get(opportunity_id)
    if payload is None:
        # 404 evita confirmar a existência de recursos de outro workspace.
        raise HTTPException(status_code=404, detail="Oportunidade não encontrada")
    return payload
