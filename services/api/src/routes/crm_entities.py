"""Rotas tenant-safe das entidades canônicas de CRM."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, get_user_membership, get_user_organization
from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember, User
from src.services.crm_360_service import Crm360Service
from src.services.crm_entity_command_service import (
    CrmEntityCommandService,
    CrmEntityConflict,
    CrmEntityForbidden,
    CrmEntityValidation,
)

router = APIRouter(tags=["crm-360"])


class CompanyPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_updated_at: str
    company_name: str | None = None
    name: str | None = None
    website: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    category: str | None = None
    company_linkedin_url: str | None = None
    instagram_url: str | None = None


class PersonPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_updated_at: str
    name: str | None = None
    role: str | None = None
    role_label: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    verification_status: str | None = None
    routability_type: str | None = None
    routable: bool | None = None
    routability_reason: str | None = None


class VerifyPersonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_updated_at: str


def _command(db: Session, org: Organization, member: OrganizationMember, user: User) -> CrmEntityCommandService:
    return CrmEntityCommandService(db, org.id, member, user)


def _handle_command_error(db: Session, exc: Exception) -> None:
    db.rollback()
    if isinstance(exc, CrmEntityForbidden):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, CrmEntityConflict):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, CrmEntityValidation):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, IntegrityError):
        raise HTTPException(status_code=409, detail="A alteração conflita com uma identidade canônica já existente") from exc
    raise exc


@router.get("/companies/{company_id}/360")
def get_company_360(
    company_id: str,
    db: Session = Depends(get_db),
    organization: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    payload = Crm360Service(db, organization.id, member).company(company_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    return payload


@router.patch("/companies/{company_id}/360")
def patch_company_360(
    company_id: str,
    body: CompanyPatch,
    db: Session = Depends(get_db),
    organization: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
    user: User = Depends(get_current_user),
):
    values: dict[str, Any] = body.model_dump(exclude={"expected_updated_at"}, exclude_unset=True)
    try:
        _command(db, organization, member, user).update_company(
            company_id, expected_updated_at=body.expected_updated_at, values=values,
        )
    except (CrmEntityForbidden, CrmEntityConflict, CrmEntityValidation, LookupError, IntegrityError) as exc:
        _handle_command_error(db, exc)
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
    payload = Crm360Service(db, organization.id, member).person(person_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada")
    return payload


@router.patch("/people/{person_id}/360")
def patch_person_360(
    person_id: str,
    body: PersonPatch,
    db: Session = Depends(get_db),
    organization: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
    user: User = Depends(get_current_user),
):
    values: dict[str, Any] = body.model_dump(exclude={"expected_updated_at"}, exclude_unset=True)
    try:
        _command(db, organization, member, user).update_person(
            person_id, expected_updated_at=body.expected_updated_at, values=values,
        )
    except (CrmEntityForbidden, CrmEntityConflict, CrmEntityValidation, LookupError, IntegrityError) as exc:
        _handle_command_error(db, exc)
    payload = Crm360Service(db, organization.id, member).person(person_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada")
    return payload


@router.post("/people/{person_id}/verify")
def verify_person_360(
    person_id: str,
    body: VerifyPersonRequest,
    db: Session = Depends(get_db),
    organization: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
    user: User = Depends(get_current_user),
):
    try:
        _command(db, organization, member, user).human_verify_person(
            person_id, expected_updated_at=body.expected_updated_at,
        )
    except (CrmEntityForbidden, CrmEntityConflict, CrmEntityValidation, LookupError) as exc:
        _handle_command_error(db, exc)
    payload = Crm360Service(db, organization.id, member).person(person_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada")
    return payload
