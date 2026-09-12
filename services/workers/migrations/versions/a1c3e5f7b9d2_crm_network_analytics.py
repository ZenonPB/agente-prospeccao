"""CRM sync, prospect lists and provider quality snapshots.

Revision ID: a1c3e5f7b9d2
Revises: 9f1a3c5e7b8d
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1c3e5f7b9d2"
down_revision: Union[str, Sequence[str], None] = "9f1a3c5e7b8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crm_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("sync_mode", sa.String(24), nullable=False, server_default="manual"),
        sa.Column("secret_key_name", sa.String(96), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cursor", sa.String(500), nullable=True),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_health_status", sa.String(32), nullable=True),
        sa.Column("last_health_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "provider", name="uq_crm_connections_org_provider"),
    )
    op.create_index("ix_crm_connections_org_enabled", "crm_connections", ["organization_id", "enabled"])

    op.create_table(
        "crm_external_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("local_entity_id", sa.String(80), nullable=False),
        sa.Column("remote_entity_id", sa.String(160), nullable=False),
        sa.Column("remote_version", sa.String(160), nullable=True),
        sa.Column("last_local_hash", sa.String(64), nullable=True),
        sa.Column("last_remote_hash", sa.String(64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "provider", "entity_type", "local_entity_id", name="uq_crm_links_local"),
        sa.UniqueConstraint("organization_id", "provider", "entity_type", "remote_entity_id", name="uq_crm_links_remote"),
    )
    op.create_index("ix_crm_links_org_provider", "crm_external_links", ["organization_id", "provider"])

    op.create_table(
        "crm_sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connection_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="RUNNING"),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("conflicts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_crm_sync_runs_org_idempotency"),
    )
    op.create_index("ix_crm_sync_runs_org_started", "crm_sync_runs", ["organization_id", "started_at"])

    op.create_table(
        "prospect_lists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "name", name="uq_prospect_lists_org_name"),
    )
    op.create_index("ix_prospect_lists_org_active", "prospect_lists", ["organization_id", "active"])

    op.create_table(
        "prospect_list_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("list_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("prospect_lists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="manual"),
        sa.Column("source_ref", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("list_id", "lead_id", name="uq_prospect_list_members_list_lead"),
    )
    op.create_index("ix_prospect_list_members_org_list", "prospect_list_members", ["organization_id", "list_id"])

    op.create_table(
        "provider_quality_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("capability", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("window_key", sa.String(32), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coverage", sa.Float(), nullable=True),
        sa.Column("precision", sa.Float(), nullable=True),
        sa.Column("commercial_yield", sa.Float(), nullable=True),
        sa.Column("cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("revenue", sa.Float(), nullable=False, server_default="0"),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "capability", "provider", "window_key", name="uq_provider_quality_window"),
    )
    op.create_index("ix_provider_quality_org_capability", "provider_quality_snapshots", ["organization_id", "capability"])


def downgrade() -> None:
    op.drop_index("ix_provider_quality_org_capability", table_name="provider_quality_snapshots")
    op.drop_table("provider_quality_snapshots")
    op.drop_index("ix_prospect_list_members_org_list", table_name="prospect_list_members")
    op.drop_table("prospect_list_members")
    op.drop_index("ix_prospect_lists_org_active", table_name="prospect_lists")
    op.drop_table("prospect_lists")
    op.drop_index("ix_crm_sync_runs_org_started", table_name="crm_sync_runs")
    op.drop_table("crm_sync_runs")
    op.drop_index("ix_crm_links_org_provider", table_name="crm_external_links")
    op.drop_table("crm_external_links")
    op.drop_index("ix_crm_connections_org_enabled", table_name="crm_connections")
    op.drop_table("crm_connections")
