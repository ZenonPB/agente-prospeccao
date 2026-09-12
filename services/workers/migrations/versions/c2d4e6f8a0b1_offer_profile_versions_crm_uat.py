"""OfferProfile versioning/rollback and CRM certification evidence.

Revision ID: c2d4e6f8a0b1
Revises: a1c3e5f7b9d2
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c2d4e6f8a0b1"
down_revision: Union[str, Sequence[str], None] = "a1c3e5f7b9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "offer_profile_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("offer_key", sa.String(64), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("profile_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_proposal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("controlled_learning_proposals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rollback_of_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("offer_profile_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("activated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "offer_key", "version", name="uq_offer_profile_versions_org_offer_version"),
    )
    op.create_index(
        "ix_offer_profile_versions_org_offer_active",
        "offer_profile_versions",
        ["organization_id", "offer_key", "is_active"],
    )
    op.create_index(
        "uq_offer_profile_versions_one_active",
        "offer_profile_versions",
        ["organization_id", "offer_key"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "offer_profile_activations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("offer_key", sa.String(64), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("offer_profile_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("previous_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("offer_profile_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_offer_profile_activations_org_offer_created",
        "offer_profile_activations",
        ["organization_id", "offer_key", "created_at"],
    )

    op.create_table(
        "crm_certification_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("checks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("adapter_version", sa.String(16), nullable=False),
        sa.Column("tested_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_crm_certification_org_connection_created",
        "crm_certification_runs",
        ["organization_id", "connection_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_crm_certification_org_connection_created", table_name="crm_certification_runs")
    op.drop_table("crm_certification_runs")
    op.drop_index("ix_offer_profile_activations_org_offer_created", table_name="offer_profile_activations")
    op.drop_table("offer_profile_activations")
    op.drop_index("uq_offer_profile_versions_one_active", table_name="offer_profile_versions")
    op.drop_index("ix_offer_profile_versions_org_offer_active", table_name="offer_profile_versions")
    op.drop_table("offer_profile_versions")
