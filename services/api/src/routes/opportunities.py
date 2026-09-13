"""Rotas da Opportunity 360: leitura agregada e comandos comerciais."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, get_user_membership, get_user_organization
from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember, User
from src.services.opportunity_360_service import Opportunity360Service
from src.services.opportunity_command_service import (
    OpportunityCommandService,
    OpportunityForbidden,
    OpportunityNotFound,
    OpportunityValidation,
)

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


class Opportunity360Patch(BaseModel):
    owner_user_id: str | None = None
    status: str | None = None
    negotiation_stage: str | None = None
    value: float | None = Field(None, ge=0)
    expected_close_date: str | None = None
    next_action_at: str | None = None
    lost_reason: str | None = None
    notes: str | None = Field(None, max_length=10_000)


class OpportunityTaskCreate(BaseModel):
    client_request_id: str = Field(..., min_length=8, max_length=80)
    title: str = Field(..., min_length=1, max_length=180)
    description: str | None = Field(None, max_length=4000)
    task_type: str = Field("FOLLOW_UP", min_length=2, max_length=32)
    due_at: str | None = None
    owner_user_id: str | None = None


class OpportunityTaskPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=180)
    description: str | None = Field(None, max_length=4000)
    due_at: str | None = None
    owner_user_id: str | None = None
    status: Literal["OPEN", "COMPLETED", "DISMISSED"] | None = None


def _commands(db: Session, organization: Organization, member: OrganizationMember, user: User):
    return OpportunityCommandService(db, organization.id, member, user)


def _translate_command_error(exc: Exception):
    if isinstance(exc, OpportunityNotFound):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, OpportunityForbidden):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, OpportunityValidation):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


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


@router.patch("/{opportunity_id}/360")
def patch_opportunity_360(
    opportunity_id: str,
    body: Opportunity360Patch,
    db: Session = Depends(get_db),
    organization: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
    user: User = Depends(get_current_user),
):
    """Edita o estado comercial canônico usado pela Opportunity 360."""
    try:
        return _commands(db, organization, member, user).update(
            opportunity_id,
            body.model_dump(exclude_unset=True),
        )
    except (OpportunityNotFound, OpportunityForbidden, OpportunityValidation) as exc:
        _translate_command_error(exc)


@router.post("/{opportunity_id}/tasks", status_code=status.HTTP_201_CREATED)
def create_opportunity_task(
    opportunity_id: str,
    body: OpportunityTaskCreate,
    db: Session = Depends(get_db),
    organization: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
    user: User = Depends(get_current_user),
):
    """Cria tarefa idempotente vinculada ao Lead desta oportunidade."""
    try:
        return _commands(db, organization, member, user).create_task(
            opportunity_id,
            body.model_dump(),
        )
    except (OpportunityNotFound, OpportunityForbidden, OpportunityValidation) as exc:
        _translate_command_error(exc)


@router.patch("/{opportunity_id}/tasks/{task_id}")
def patch_opportunity_task(
    opportunity_id: str,
    task_id: str,
    body: OpportunityTaskPatch,
    db: Session = Depends(get_db),
    organization: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
    user: User = Depends(get_current_user),
):
    """Atualiza uma tarefa existente sem criar segunda fonte de verdade."""
    try:
        return _commands(db, organization, member, user).update_task(
            opportunity_id,
            task_id,
            body.model_dump(exclude_unset=True),
        )
    except (OpportunityNotFound, OpportunityForbidden, OpportunityValidation) as exc:
        _translate_command_error(exc)
