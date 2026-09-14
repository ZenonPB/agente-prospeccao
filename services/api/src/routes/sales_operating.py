"""Endpoints da Central Comercial.

Contratos voltados à operação diária: fila priorizada, busca global, visões
salvas, ações em massa e export. Tudo é organization-scoped.
"""
from __future__ import annotations

import csv
import io
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.crm_models import CrmEntityAudit, LeadCrmMetadata
from src.auth.dependencies import get_current_user, get_user_membership, get_user_organization
from src.db.dependencies import get_db
from src.db.models import Lead, Organization, OrganizationMember, User
from src.services.lead_bulk_command_service import (
    BulkCommandConflict,
    BulkCommandForbidden,
    BulkCommandValidation,
    LeadBulkCommandService,
)
from src.services.org_service import consultant_lead_scope
from src.services.sales_operating_bulk_service import (
    OperatingBulkConflict,
    OperatingBulkForbidden,
    OperatingBulkValidation,
    SalesOperatingBulkService,
)
from src.services.sales_operating_service import (
    SalesOperatingForbidden,
    SalesOperatingService,
    SalesOperatingValidation,
    serialize_saved_view,
)

router = APIRouter(prefix="/operating", tags=["crm-operating"])


class SavedViewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=2, max_length=120)
    view_kind: str = "crm"
    filters: dict[str, Any] = Field(default_factory=dict)
    shared: bool = False


class BulkTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lead_ids: list[str] = Field(..., min_length=1, max_length=100)
    expected_updated_at: dict[str, str]
    title: str = Field(..., min_length=1, max_length=180)
    description: str | None = Field(default=None, max_length=2000)
    due_at: str | None = None
    task_type: str = Field(default="FOLLOW_UP", min_length=1, max_length=32)


class BulkTaskExecute(BulkTaskRequest):
    idempotency_key: str = Field(..., min_length=8, max_length=160)


class OperatingBulkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operation: str
    lead_ids: list[str] = Field(..., min_length=1, max_length=100)
    expected_updated_at: dict[str, str]
    negotiation_stage: str | None = None
    campaign_id: str | None = None
    tag: str | None = None
    sequence_id: str | None = None


class OperatingBulkExecute(OperatingBulkRequest):
    idempotency_key: str = Field(..., min_length=8, max_length=160)


class ExportSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lead_ids: list[str] = Field(..., min_length=1, max_length=500)


def _service(db: Session, org: Organization, member: OrganizationMember, user: User) -> SalesOperatingService:
    return SalesOperatingService(db, org.id, member, user)


def _task_payload(body: BulkTaskRequest) -> dict[str, Any]:
    return {
        "operation": "create_task",
        "lead_ids": body.lead_ids,
        "expected_updated_at": body.expected_updated_at,
        "task_type": body.task_type,
        "task_title": body.title,
        "task_description": body.description,
        "task_due_at": body.due_at,
    }


@router.get("/queue")
def operating_queue(
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    return _service(db, org, member, user).queue(limit=limit)


@router.get("/search")
def operating_search(
    q: str = Query(..., min_length=2, max_length=120),
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    try:
        return _service(db, org, member, user).search(q, limit=limit)
    except SalesOperatingValidation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/saved-views")
def list_saved_views(
    view_kind: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    try:
        items = _service(db, org, member, user).list_saved_views(view_kind=view_kind)
        return {"items": [serialize_saved_view(item, user.id) for item in items]}
    except SalesOperatingValidation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/saved-views", status_code=201)
def create_saved_view(
    body: SavedViewCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    service = _service(db, org, member, user)
    try:
        item = service.create_saved_view(name=body.name, view_kind=body.view_kind, filters=body.filters, shared=body.shared)
        return serialize_saved_view(item, user.id)
    except SalesOperatingForbidden as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except SalesOperatingValidation as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe uma visão com esse nome") from exc


@router.delete("/saved-views/{view_id}", status_code=204)
def delete_saved_view(
    view_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    try:
        _service(db, org, member, user).delete_saved_view(view_id)
    except SalesOperatingForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except SalesOperatingValidation as exc:
        raise HTTPException(status_code=404 if "não encontrada" in str(exc) else 422, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/bulk-task/preview")
def preview_bulk_task(
    body: BulkTaskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    try:
        return LeadBulkCommandService(db, org.id, member, user).preview(_task_payload(body))
    except BulkCommandForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except BulkCommandValidation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/bulk-task/execute")
def execute_bulk_task(
    body: BulkTaskExecute,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    try:
        return LeadBulkCommandService(db, org.id, member, user).execute(_task_payload(body), body.idempotency_key)
    except BulkCommandConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BulkCommandForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except BulkCommandValidation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/bulk/preview")
def preview_operating_bulk(
    body: OperatingBulkRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    try:
        return SalesOperatingBulkService(db, org.id, member, user).preview(body.model_dump(exclude_none=True))
    except OperatingBulkForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except OperatingBulkValidation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/bulk/execute")
def execute_operating_bulk(
    body: OperatingBulkExecute,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    payload = body.model_dump(exclude={"idempotency_key"}, exclude_none=True)
    try:
        return SalesOperatingBulkService(db, org.id, member, user).execute(payload, body.idempotency_key)
    except OperatingBulkConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OperatingBulkForbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except OperatingBulkValidation as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/export")
def export_operating_selection(
    body: ExportSelectionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(get_user_membership),
):
    try:
        ids = [uuid.UUID(item) for item in body.lead_ids]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="lead_ids contém identificador inválido") from exc
    query = db.query(Lead).filter(Lead.organization_id == org.id, Lead.id.in_(ids))
    rows = consultant_lead_scope(member, query).order_by(Lead.company_name.asc(), Lead.id.asc()).all()
    visible_ids = {row.id for row in rows}
    if visible_ids != set(ids):
        # Fail closed: não revela quais ids estão fora da carteira/workspace.
        raise HTTPException(status_code=404, detail="Uma ou mais oportunidades não foram encontradas")
    metadata = {
        item.lead_id: item
        for item in db.query(LeadCrmMetadata).filter(
            LeadCrmMetadata.organization_id == org.id,
            LeadCrmMetadata.lead_id.in_(ids),
        ).all()
    }
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\n")
    writer.writerow([
        "Empresa", "Cidade", "UF", "Status", "Estágio", "Score", "Valor",
        "Responsável", "Próxima ação", "Tags", "Arquivado",
    ])
    for row in rows:
        meta = metadata.get(row.id)
        writer.writerow([
            row.company_name,
            row.city or "",
            row.state or "",
            getattr(row.status, "value", row.status) or "",
            getattr(row.negotiation_stage, "value", row.negotiation_stage) or "",
            row.qualification_score if row.qualification_score is not None else "",
            str(row.value) if row.value is not None else "",
            str(row.assigned_to_id) if row.assigned_to_id else "",
            row.next_action_at.isoformat() if row.next_action_at else "",
            ", ".join(meta.tags or []) if meta else "",
            "sim" if meta and meta.archived_at else "não",
        ])
    db.add(CrmEntityAudit(
        organization_id=org.id,
        actor_id=user.id,
        entity_type="lead_selection",
        entity_id="multiple",
        action="EXPORT",
        changes={"lead_ids": [str(item) for item in ids], "count": len(ids)},
    ))
    db.commit()
    content = "\ufeff" + output.getvalue()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="crm-export.csv"'},
    )
