"""Modelos persistentes de engagement, tarefas e workflows comerciais."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.models import Base


class SequenceTemplate(Base):
    __tablename__ = "sequence_templates"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", "version", name="uq_sequence_templates_org_name_version"),
        Index("ix_sequence_templates_org_enabled", "organization_id", "enabled"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    offer_key = Column(String(64), nullable=True)
    persona_key = Column(String(80), nullable=True)
    version = Column(Integer, nullable=False, server_default="1")
    steps = Column(JSONB, nullable=False, default=list)
    enabled = Column(Boolean, nullable=False, server_default="true")
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SequenceEnrollment(Base):
    __tablename__ = "sequence_enrollments"
    __table_args__ = (
        UniqueConstraint("sequence_id", "lead_id", name="uq_sequence_enrollments_sequence_lead"),
        Index("ix_sequence_enrollments_org_status_next", "organization_id", "status", "next_action_at"),
        Index("ix_sequence_enrollments_lead", "lead_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    sequence_id = Column(UUID(as_uuid=True), ForeignKey("sequence_templates.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    enrolled_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(24), nullable=False, server_default="ACTIVE")
    current_step_index = Column(Integer, nullable=False, server_default="0")
    pause_reason = Column(String(255), nullable=True)
    next_action_at = Column(DateTime(timezone=True), nullable=True)
    last_action_at = Column(DateTime(timezone=True), nullable=True)
    enrollment_metadata = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class SequenceExecution(Base):
    __tablename__ = "sequence_executions"
    __table_args__ = (
        UniqueConstraint("enrollment_id", "step_index", name="uq_sequence_executions_enrollment_step"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_sequence_executions_org_idempotency"),
        Index("ix_sequence_executions_org_status_scheduled", "organization_id", "status", "scheduled_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("sequence_enrollments.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    step_index = Column(Integer, nullable=False)
    step_type = Column(String(32), nullable=False)
    status = Column(String(24), nullable=False, server_default="PENDING")
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    ready_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    payload = Column(JSONB, nullable=False, default=dict)
    outcome = Column(JSONB, nullable=True)
    idempotency_key = Column(String(160), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class CommercialTask(Base):
    __tablename__ = "commercial_tasks"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_commercial_tasks_org_idempotency"),
        Index("ix_commercial_tasks_org_status_due", "organization_id", "status", "due_at"),
        Index("ix_commercial_tasks_owner_status", "owner_user_id", "status"),
        Index("ix_commercial_tasks_lead", "lead_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("sequence_enrollments.id", ondelete="SET NULL"), nullable=True)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    task_type = Column(String(32), nullable=False)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(24), nullable=False, server_default="OPEN")
    source = Column(String(32), nullable=False, server_default="sequence")
    source_ref = Column(String(160), nullable=True)
    idempotency_key = Column(String(160), nullable=False)
    task_metadata = Column(JSONB, nullable=False, default=dict)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class NextBestActionDecision(Base):
    __tablename__ = "next_best_action_decisions"
    __table_args__ = (
        UniqueConstraint("organization_id", "lead_id", "fingerprint", name="uq_nba_decisions_org_lead_fingerprint"),
        Index("ix_nba_decisions_org_lead_created", "organization_id", "lead_id", "created_at"),
        Index("ix_nba_decisions_org_status_deadline", "organization_id", "status", "deadline"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    enrollment_id = Column(UUID(as_uuid=True), ForeignKey("sequence_enrollments.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(40), nullable=False)
    why = Column(String(255), nullable=False)
    confidence = Column(Float, nullable=False)
    evidence = Column(JSONB, nullable=False, default=list)
    deadline = Column(DateTime(timezone=True), nullable=True)
    offer_key = Column(String(64), nullable=True)
    fingerprint = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, server_default="PENDING")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", "version", name="uq_workflow_definitions_org_name_version"),
        Index("ix_workflow_definitions_org_trigger_enabled", "organization_id", "trigger_type", "enabled"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    trigger_type = Column(String(48), nullable=False)
    conditions = Column(JSONB, nullable=False, default=list)
    actions = Column(JSONB, nullable=False, default=list)
    version = Column(Integer, nullable=False, server_default="1")
    enabled = Column(Boolean, nullable=False, server_default="true")
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "workflow_id", "event_key", name="uq_workflow_runs_org_workflow_event"),
        Index("ix_workflow_runs_org_status_started", "organization_id", "status", "started_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False)
    trigger_type = Column(String(48), nullable=False)
    event_key = Column(String(160), nullable=False)
    entity_type = Column(String(32), nullable=True)
    entity_id = Column(String(80), nullable=True)
    status = Column(String(24), nullable=False, server_default="RUNNING")
    context = Column(JSONB, nullable=False, default=dict)
    action_results = Column(JSONB, nullable=False, default=list)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
