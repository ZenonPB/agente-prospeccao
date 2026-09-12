"""Modelos persistentes de inteligência comercial e automação de prospecção.

Este módulo pertence aos workers, que são a fonte única do schema persistido.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.models import Base


class SavedProspectingSearch(Base):
    __tablename__ = "saved_prospecting_searches"
    __table_args__ = (Index("ix_saved_searches_org_enabled", "organization_id", "enabled"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    owner_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(160), nullable=False)
    offer_key = Column(String(64), nullable=True)
    filters = Column(JSONB, nullable=False, default=dict)
    schedule = Column(String(64), nullable=False, server_default="manual")
    notification_policy = Column(JSONB, nullable=False, default=dict)
    enabled = Column(Boolean, nullable=False, server_default="true")
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ProspectingAlert(Base):
    __tablename__ = "prospecting_alerts"
    __table_args__ = (
        UniqueConstraint("organization_id", "fingerprint", name="uq_prospecting_alerts_org_fingerprint"),
        Index("ix_prospecting_alerts_org_status_created", "organization_id", "status", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    saved_search_id = Column(UUID(as_uuid=True), ForeignKey("saved_prospecting_searches.id", ondelete="SET NULL"), nullable=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("event_opportunities.id", ondelete="CASCADE"), nullable=True)
    kind = Column(String(48), nullable=False, server_default="saved_search_match")
    title = Column(String(255), nullable=False)
    reason = Column(Text, nullable=True)
    score = Column(Float, nullable=True)
    evidence = Column(JSONB, nullable=True)
    fingerprint = Column(String(64), nullable=False)
    status = Column(String(24), nullable=False, server_default="new")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class EventSeries(Base):
    __tablename__ = "event_series"
    __table_args__ = (
        UniqueConstraint("organization_id", "series_key", name="uq_event_series_org_key"),
        Index("ix_event_series_org_window", "organization_id", "updated_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    series_key = Column(String(180), nullable=False)
    name = Column(String(255), nullable=False)
    family = Column(String(64), nullable=True)
    recurrence_confidence = Column(Float, nullable=False, server_default="0")
    previous_event_id = Column(UUID(as_uuid=True), ForeignKey("event_opportunities.id", ondelete="SET NULL"), nullable=True)
    latest_event_id = Column(UUID(as_uuid=True), ForeignKey("event_opportunities.id", ondelete="SET NULL"), nullable=True)
    expected_next_window = Column(JSONB, nullable=True)
    series_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class CaseStudy(Base):
    __tablename__ = "case_studies"
    __table_args__ = (Index("ix_case_studies_org_offer_active", "organization_id", "offer_key", "active"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    offer_key = Column(String(64), nullable=False)
    title = Column(String(180), nullable=False)
    segments = Column(JSONB, nullable=False, default=list)
    problem = Column(Text, nullable=False)
    solution = Column(Text, nullable=False)
    proof = Column(Text, nullable=True)
    assets = Column(JSONB, nullable=True)
    active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ProspectingAgentState(Base):
    __tablename__ = "prospecting_agent_states"
    __table_args__ = (
        UniqueConstraint("organization_id", "lead_id", name="uq_agent_state_org_lead"),
        Index("ix_agent_state_org_state", "organization_id", "state"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    state = Column(String(32), nullable=False, server_default="DISCOVERED")
    reason = Column(String(255), nullable=True)
    evidence = Column(JSONB, nullable=True)
    history = Column(JSONB, nullable=False, default=list)
    changed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
