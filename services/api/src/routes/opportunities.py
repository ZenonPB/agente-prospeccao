"""Rotas de leitura agregada para o CRM comercial."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.dependencies import get_user_membership, get_user_organization
from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember
from src.services.crm_360_service import Crm360Service
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


@router.get("/companies/{company_id}/360")
def get_company_360(
    company_id: str,
    db: Session = Depends(get_db),
    organization: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Retorna conta, pessoas, oportunidades e histórico visíveis da empresa."""
    payload = Crm360Service(db, organization.id, member).company(company_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    return payload


@router.get("/people/{person_id}/360")
def get_person_360(
    person_id: str,
    db: Session = Depends(get_db),
    organization: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    """Retorna pessoa, conta e histórico comercial visíveis no workspace."""
    payload = Crm360Service(db, organization.id, member).person(person_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada")
    return payload
