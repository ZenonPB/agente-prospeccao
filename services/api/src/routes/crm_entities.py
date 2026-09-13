"""Rotas read-only das entidades canônicas de CRM."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.dependencies import get_user_membership, get_user_organization
from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember
from src.services.crm_360_service import Crm360Service

router = APIRouter(tags=["crm-360"])


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
        # Fail-closed: não confirma existência em outro workspace/carteira.
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
