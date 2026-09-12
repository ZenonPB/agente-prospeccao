"""Rotas de sequences, tarefas, próxima ação e workflows comerciais."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, get_user_organization, require_analyst, require_manager
from src.db.dependencies import get_db
from src.db.models import Lead, Organization, OrganizationMember, User
from database.engagement_models import (
    CommercialTask,
    NextBestActionDecision,
    SequenceEnrollment,
    SequenceExecution,
    SequenceTemplate,
    WorkflowDefinition,
    WorkflowRun,
)
from src.services.engagement_service import NextBestActionDecisionService, SequenceService
from src.services.webhook_outbound_service import enqueue_webhook
from src.services.workflow_service import TRIGGERS, WorkflowService

router = APIRouter(prefix="/engagement", tags=["engagement"])


class SequenceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    description: str | None = Field(None, max_length=4000)
    offer_key: str | None = Field(None, max_length=64)
    persona_key: str | None = Field(None, max_length=80)
    steps: list[dict[str, Any]] = Field(..., min_length=1, max_length=30)


class EnrollmentCreate(BaseModel):
    sequence_id: str
    lead_id: str
    person_id: str | None = None


class ExecutionComplete(BaseModel):
    outcome: dict[str, Any] = Field(default_factory=dict)


class TaskPatch(BaseModel):
    status: Literal["OPEN", "COMPLETED", "DISMISSED"]


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    description: str | None = Field(None, max_length=4000)
    trigger_type: str = Field(..., min_length=2, max_length=48)
    conditions: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    actions: list[dict[str, Any]] = Field(..., min_length=1, max_length=20)


class WorkflowEvent(BaseModel):
    trigger_type: str = Field(..., min_length=2, max_length=48)
    event_key: str = Field(..., min_length=4, max_length=160)
    context: dict[str, Any] = Field(default_factory=dict)


def _sequence_dict(row: SequenceTemplate) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "name": row.name,
        "description": row.description,
        "offer_key": row.offer_key,
        "persona_key": row.persona_key,
        "version": row.version,
        "steps": row.steps or [],
        "enabled": row.enabled,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _enrollment_dict(row: SequenceEnrollment) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "sequence_id": str(row.sequence_id),
        "lead_id": str(row.lead_id),
        "person_id": str(row.person_id) if row.person_id else None,
        "status": row.status,
        "current_step_index": row.current_step_index,
        "pause_reason": row.pause_reason,
        "next_action_at": row.next_action_at.isoformat() if row.next_action_at else None,
        "last_action_at": row.last_action_at.isoformat() if row.last_action_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _execution_dict(row: SequenceExecution) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "enrollment_id": str(row.enrollment_id),
        "lead_id": str(row.lead_id),
        "step_index": row.step_index,
        "step_type": row.step_type,
        "status": row.status,
        "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
        "ready_at": row.ready_at.isoformat() if row.ready_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "payload": row.payload or {},
        "outcome": row.outcome,
    }


def _task_dict(row: CommercialTask) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "lead_id": str(row.lead_id),
        "person_id": str(row.person_id) if row.person_id else None,
        "enrollment_id": str(row.enrollment_id) if row.enrollment_id else None,
        "owner_user_id": str(row.owner_user_id) if row.owner_user_id else None,
        "task_type": row.task_type,
        "title": row.title,
        "description": row.description,
        "due_at": row.due_at.isoformat() if row.due_at else None,
        "status": row.status,
        "source": row.source,
        "metadata": row.task_metadata or {},
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


def _decision_dict(row: NextBestActionDecision) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "lead_id": str(row.lead_id),
        "action": row.action,
        "why": row.why,
        "confidence": row.confidence,
        "evidence": row.evidence or [],
        "deadline": row.deadline.isoformat() if row.deadline else None,
        "offer_key": row.offer_key,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _workflow_dict(row: WorkflowDefinition) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "name": row.name,
        "description": row.description,
        "trigger_type": row.trigger_type,
        "conditions": row.conditions or [],
        "actions": row.actions or [],
        "version": row.version,
        "enabled": row.enabled,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _run_dict(row: WorkflowRun) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "workflow_id": str(row.workflow_id),
        "trigger_type": row.trigger_type,
        "event_key": row.event_key,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "status": row.status,
        "action_results": row.action_results or [],
        "error_message": row.error_message,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


@router.get("/sequences")
def list_sequences(
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    return {"items": [_sequence_dict(row) for row in SequenceService(db, org.id).list_templates()]}


@router.post("/sequences", status_code=status.HTTP_201_CREATED)
def create_sequence(
    body: SequenceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    try:
        row = SequenceService(db, org.id).create_template(
            name=body.name,
            description=body.description,
            offer_key=body.offer_key,
            persona_key=body.persona_key,
            steps=body.steps,
            created_by_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _sequence_dict(row)


@router.post("/enrollments", status_code=status.HTTP_201_CREATED)
def create_enrollment(
    body: EnrollmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    try:
        row = SequenceService(db, org.id).enroll(
            sequence_id=body.sequence_id,
            lead_id=body.lead_id,
            person_id=body.person_id,
            enrolled_by_id=user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _enrollment_dict(row)


@router.get("/enrollments")
def list_enrollments(
    enrollment_status: str | None = Query(None, alias="status", max_length=24),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    rows = SequenceService(db, org.id).list_enrollments(status=enrollment_status, limit=limit)
    return {"items": [_enrollment_dict(row) for row in rows]}


@router.get("/enrollments/{enrollment_id}/executions")
def list_executions(
    enrollment_id: str,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    enrollment = db.query(SequenceEnrollment).filter(
        SequenceEnrollment.id == enrollment_id,
        SequenceEnrollment.organization_id == org.id,
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Inscrição não encontrada")
    rows = db.query(SequenceExecution).filter(
        SequenceExecution.organization_id == org.id,
        SequenceExecution.enrollment_id == enrollment.id,
    ).order_by(SequenceExecution.step_index.asc()).all()
    return {"items": [_execution_dict(row) for row in rows]}


@router.post("/enrollments/{enrollment_id}/resume")
def resume_enrollment(
    enrollment_id: str,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    try:
        row = SequenceService(db, org.id).resume(enrollment_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _enrollment_dict(row)


@router.post("/sequences/process-due")
def process_due_sequences(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    return SequenceService(db, org.id).process_due(limit=limit)


@router.post("/executions/{execution_id}/complete")
def complete_execution(
    execution_id: str,
    body: ExecutionComplete,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    try:
        row = SequenceService(db, org.id).complete_execution(execution_id=execution_id, outcome=body.outcome)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _execution_dict(row)


@router.get("/tasks")
def list_tasks(
    task_status: str | None = Query("OPEN", alias="status", max_length=24),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    query = db.query(CommercialTask).filter(CommercialTask.organization_id == org.id)
    if task_status:
        query = query.filter(CommercialTask.status == task_status)
    rows = query.order_by(CommercialTask.due_at.asc().nullslast(), CommercialTask.created_at.desc()).limit(limit).all()
    return {"items": [_task_dict(row) for row in rows]}


@router.patch("/tasks/{task_id}")
def patch_task(
    task_id: str,
    body: TaskPatch,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    task = db.query(CommercialTask).filter(
        CommercialTask.id == task_id,
        CommercialTask.organization_id == org.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    task.status = body.status
    if body.status == "COMPLETED":
        from datetime import datetime, timezone
        task.completed_at = datetime.now(timezone.utc)
        if task.source_ref:
            execution = db.query(SequenceExecution).filter(
                SequenceExecution.id == task.source_ref,
                SequenceExecution.organization_id == org.id,
            ).first()
            if execution and execution.status == "READY":
                db.commit()
                SequenceService(db, org.id).complete_execution(execution_id=execution.id, outcome={"task_completed": True})
                db.refresh(task)
                return _task_dict(task)
    db.commit()
    db.refresh(task)
    return _task_dict(task)


@router.post("/next-best-action/{lead_id}")
def refresh_next_best_action(
    lead_id: str,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    try:
        row = NextBestActionDecisionService(db, org.id).refresh(lead_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _decision_dict(row)


@router.get("/next-best-action/{lead_id}")
def list_next_best_action_decisions(
    lead_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == org.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    rows = db.query(NextBestActionDecision).filter(
        NextBestActionDecision.organization_id == org.id,
        NextBestActionDecision.lead_id == lead.id,
    ).order_by(NextBestActionDecision.created_at.desc()).limit(limit).all()
    return {"items": [_decision_dict(row) for row in rows]}


@router.get("/workflows")
def list_workflows(
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    return {"items": [_workflow_dict(row) for row in WorkflowService(db, org.id).list_definitions()], "triggers": sorted(TRIGGERS)}


@router.post("/workflows", status_code=status.HTTP_201_CREATED)
def create_workflow(
    body: WorkflowCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    try:
        row = WorkflowService(db, org.id).create_definition(
            name=body.name,
            description=body.description,
            trigger_type=body.trigger_type,
            conditions=body.conditions,
            actions=body.actions,
            created_by_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _workflow_dict(row)


@router.post("/workflows/run-event")
def run_workflow_event(
    body: WorkflowEvent,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    def dispatch(event: str, data: dict[str, Any]) -> bool:
        return enqueue_webhook(background_tasks, db, org.id, event, data)

    try:
        rows = WorkflowService(db, org.id).run_event(
            trigger_type=body.trigger_type,
            event_key=body.event_key,
            context=body.context,
            webhook_dispatcher=dispatch,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"items": [_run_dict(row) for row in rows]}


@router.get("/workflow-runs")
def list_workflow_runs(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    org: Organization = Depends(get_user_organization),
):
    rows = db.query(WorkflowRun).filter(
        WorkflowRun.organization_id == org.id,
    ).order_by(WorkflowRun.started_at.desc()).limit(limit).all()
    return {"items": [_run_dict(row) for row in rows]}


@router.delete("/workflows/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def disable_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_manager()),
    org: Organization = Depends(get_user_organization),
):
    row = db.query(WorkflowDefinition).filter(
        WorkflowDefinition.id == workflow_id,
        WorkflowDefinition.organization_id == org.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Workflow não encontrado")
    row.enabled = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
