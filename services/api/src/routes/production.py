from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, get_user_organization, require_manager
from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember, User
from src.services.block_d_service import BlockDService, CampaignReleaseRequest

router = APIRouter(prefix="/production", tags=["production-readiness"])


class CampaignReleaseBody(BaseModel):
    mode: Literal["DRY_RUN", "REHEARSAL", "LIVE_AUTHORIZED"] = "DRY_RUN"
    provider_opt_in: bool = False
    authorization_note: str | None = Field(None, max_length=500)
    cost_cap_brl: float | None = Field(None, ge=0)
    max_contacts: int = Field(30, ge=1, le=500)


def _service(db: Session, org: Organization) -> BlockDService:
    return BlockDService(db, org.id)


@router.get("/readiness")
def readiness(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    return _service(db, org).readiness()


@router.get("/campaign-release-matrix")
def campaign_release_matrix(
    _user: User = Depends(get_current_user),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    return {
        "organization_id": str(org.id),
        "offers": BlockDService.release_matrix(),
        "live_requires": ["manager authorization", "provider opt-in", "cost cap", "tenant-scoped campaign"],
    }


@router.post("/campaigns/{campaign_id}/release-manifest")
def release_manifest(
    campaign_id: UUID,
    body: CampaignReleaseBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    request = CampaignReleaseRequest(
        campaign_id=campaign_id,
        mode=body.mode,
        provider_opt_in=body.provider_opt_in,
        authorized_by=user.id if body.mode == "LIVE_AUTHORIZED" else None,
        authorization_note=body.authorization_note,
        cost_cap_brl=body.cost_cap_brl,
        max_contacts=body.max_contacts,
    )
    try:
        return _service(db, org).release_manifest(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/campaigns/{campaign_id}/funnel")
def campaign_funnel(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    try:
        return _service(db, org).campaign_funnel(campaign_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
