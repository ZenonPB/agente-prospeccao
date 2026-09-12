"""Modelos persistentes do ciclo de learning/publicação de OfferProfile."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID

from database.models import Base


class OfferProfileVersion(Base):
    """Snapshot imutável de uma versão de OfferProfile por organização.

    `is_active` é o único estado mutável: publicação/rollback alternam qual
    snapshot está efetivamente ativo. O conteúdo em `profile_snapshot` nunca é
    alterado depois da criação.
    """

    __tablename__ = "offer_profile_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "offer_key", "version",
            name="uq_offer_profile_versions_org_offer_version",
        ),
        Index(
            "ix_offer_profile_versions_org_offer_active",
            "organization_id", "offer_key", "is_active",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    offer_key = Column(String(64), nullable=False)
    version = Column(String(32), nullable=False)
    profile_snapshot = Column(JSONB, nullable=False)
    source_proposal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("controlled_learning_proposals.id", ondelete="SET NULL"),
        nullable=True,
    )
    rollback_of_id = Column(
        UUID(as_uuid=True),
        ForeignKey("offer_profile_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active = Column(Boolean, nullable=False, server_default="false")
    activated_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    activated_at = Column(DateTime(timezone=True), nullable=True)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CRMCertificationRun(Base):
    """Evidência persistente de UAT/health read-only de uma conexão CRM."""

    __tablename__ = "crm_certification_runs"
    __table_args__ = (
        Index(
            "ix_crm_certification_org_connection_created",
            "organization_id", "connection_id", "created_at",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    connection_id = Column(
        UUID(as_uuid=True), ForeignKey("crm_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(String(32), nullable=False)
    status = Column(String(24), nullable=False)
    checks = Column(JSONB, nullable=False)
    adapter_version = Column(String(16), nullable=False)
    tested_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
