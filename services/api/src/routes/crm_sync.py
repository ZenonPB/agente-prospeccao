"""Configuração e sincronização com sistemas comerciais externos."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.crm_models import CRMConnection, CRMSyncRun
from database.learning_models import CRMCertificationRun
from src.auth.dependencies import get_current_user, get_user_organization, require_analyst, require_manager
from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember, User
from src.services.crm_sync_service import CRMSyncService

router = APIRouter(prefix="/crm-sync", tags=["crm-sync"])


class CRMConnectionUpsert(BaseModel):
    provider: Literal["pipedrive", "hubspot", "salesforce"]
    sync_mode: Literal["manual", "realtime", "scheduled"] = "manual"
    token: str | None = Field(None, min_length=8, max_length=4096)
    base_url: str | None = Field(None, max_length=500)
    enabled: bool = False


class CRMSyncRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=8, max_length=180)
    lead_id: str | None = None


def _connection(row: CRMConnection) -> dict:
    return {
        "id": str(row.id), "provider": row.provider, "sync_mode": row.sync_mode,
        "enabled": row.enabled, "base_url": row.base_url,
        "has_secret_reference": bool(row.secret_key_name),
        "last_health_status": row.last_health_status,
        "last_health_at": row.last_health_at.isoformat() if row.last_health_at else None,
        "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _run(row: CRMSyncRun) -> dict:
    return {
        "id": str(row.id), "connection_id": str(row.connection_id),
        "direction": row.direction, "status": row.status,
        "processed": row.processed, "succeeded": row.succeeded,
        "failed": row.failed, "conflicts": row.conflicts,
        "error_message": row.error_message,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


def _certification(row: CRMCertificationRun) -> dict:
    return {
        "id": str(row.id), "connection_id": str(row.connection_id),
        "provider": row.provider, "status": row.status,
        "checks": row.checks or [], "adapter_version": row.adapter_version,
        "tested_by_id": str(row.tested_by_id) if row.tested_by_id else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/connections")
async def list_connections(
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    return {"items": [_connection(row) for row in CRMSyncService(db, org.id).list_connections()]}


@router.put("/connections")
async def upsert_connection(
    body: CRMConnectionUpsert,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    try:
        row = await CRMSyncService(db, org.id).configure(
            provider=body.provider, sync_mode=body.sync_mode,
            token=body.token, base_url=body.base_url, enabled=body.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _connection(row)


@router.post("/connections/{connection_id}/health")
async def healthcheck(
    connection_id: str,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    try:
        return await CRMSyncService(db, org.id).healthcheck(connection_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/connections/{connection_id}/certify")
async def certify_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    """Executa UAT read-only real quando credencial/ambiente estiver configurado."""
    from src.services.crm_certification_service import CRMCertificationService
    try:
        row = await CRMCertificationService(db, org.id).run(connection_id, actor.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _certification(row)


@router.get("/certifications")
def list_certifications(
    connection_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    from src.services.crm_certification_service import CRMCertificationService
    rows = CRMCertificationService(db, org.id).list_runs(connection_id, limit)
    return {"items": [_certification(row) for row in rows]}


@router.post("/connections/{connection_id}/push")
async def push_lead(
    connection_id: str,
    body: CRMSyncRequest,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    if not body.lead_id:
        raise HTTPException(status_code=400, detail="Selecione uma oportunidade para sincronizar")
    try:
        return await CRMSyncService(db, org.id).push_lead(
            connection_id, body.lead_id, idempotency_key=body.idempotency_key,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/connections/{connection_id}/pull")
async def pull_changes(
    connection_id: str,
    body: CRMSyncRequest,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    try:
        return await CRMSyncService(db, org.id).pull_changes(connection_id, idempotency_key=body.idempotency_key)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs")
def list_runs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    rows = db.query(CRMSyncRun).filter(
        CRMSyncRun.organization_id == org.id,
    ).order_by(CRMSyncRun.started_at.desc()).limit(limit).all()
    return {"items": [_run(row) for row in rows]}
