"""Persistência de integrações comerciais e listas operacionais.

Credenciais nunca são armazenadas nestas tabelas. `secret_key_name` aponta para
o cofre BYOK (`organization_secrets`), mantendo configuração e segredo separados.
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.models import Base


class CRMConnection(Base):
    __tablename__ = "crm_connections"
    __table_args__ = (
        UniqueConstraint("organization_id", "provider", name="uq_crm_connections_org_provider"),
        Index("ix_crm_connections_org_enabled", "organization_id", "enabled"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(32), nullable=False)
    sync_mode = Column(String(24), nullable=False, server_default="manual")
    secret_key_name = Column(String(96), nullable=False)
    base_url = Column(String(500), nullable=True)
    enabled = Column(Boolean, nullable=False, server_default="false")
    cursor = Column(String(500), nullable=True)
    settings = Column(JSONB, nullable=False, default=dict)
    last_health_status = Column(String(32), nullable=True)
    last_health_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class CRMExternalLink(Base):
    __tablename__ = "crm_external_links"
    __table_args__ = (
        UniqueConstraint("organization_id", "provider", "entity_type", "local_entity_id", name="uq_crm_links_local"),
        UniqueConstraint("organization_id", "provider", "entity_type", "remote_entity_id", name="uq_crm_links_remote"),
        Index("ix_crm_links_org_provider", "organization_id", "provider"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(32), nullable=False)
    entity_type = Column(String(32), nullable=False)
    local_entity_id = Column(String(80), nullable=False)
    remote_entity_id = Column(String(160), nullable=False)
    remote_version = Column(String(160), nullable=True)
    last_local_hash = Column(String(64), nullable=True)
    last_remote_hash = Column(String(64), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class CRMSyncRun(Base):
    __tablename__ = "crm_sync_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_crm_sync_runs_org_idempotency"),
        Index("ix_crm_sync_runs_org_started", "organization_id", "started_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    connection_id = Column(UUID(as_uuid=True), ForeignKey("crm_connections.id", ondelete="CASCADE"), nullable=False)
    direction = Column(String(16), nullable=False)
    status = Column(String(24), nullable=False, server_default="RUNNING")
    idempotency_key = Column(String(180), nullable=False)
    processed = Column(Integer, nullable=False, server_default="0")
    succeeded = Column(Integer, nullable=False, server_default="0")
    failed = Column(Integer, nullable=False, server_default="0")
    conflicts = Column(Integer, nullable=False, server_default="0")
    result = Column(JSONB, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class ProspectList(Base):
    __tablename__ = "prospect_lists"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_prospect_lists_org_name"),
        Index("ix_prospect_lists_org_active", "organization_id", "active"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(160), nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, server_default="true")
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ProspectListMember(Base):
    __tablename__ = "prospect_list_members"
    __table_args__ = (
        UniqueConstraint("list_id", "lead_id", name="uq_prospect_list_members_list_lead"),
        Index("ix_prospect_list_members_org_list", "organization_id", "list_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    list_id = Column(UUID(as_uuid=True), ForeignKey("prospect_lists.id", ondelete="CASCADE"), nullable=False)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(32), nullable=False, server_default="manual")
    source_ref = Column(String(160), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProviderQualitySnapshot(Base):
    __tablename__ = "provider_quality_snapshots"
    __table_args__ = (
        UniqueConstraint("organization_id", "capability", "provider", "window_key", name="uq_provider_quality_window"),
        Index("ix_provider_quality_org_capability", "organization_id", "capability"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    capability = Column(String(64), nullable=False)
    provider = Column(String(80), nullable=False)
    window_key = Column(String(32), nullable=False)
    sample_size = Column(Integer, nullable=False, server_default="0")
    coverage = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    commercial_yield = Column(Float, nullable=True)
    cost = Column(Float, nullable=False, server_default="0")
    revenue = Column(Float, nullable=False, server_default="0")
    calculated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
