"""Persist offer excellence and continuous prospecting primitives.

Revision ID: 7d9e1f3a5b6c
Revises: 6c8d0e2f4a5b
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "7d9e1f3a5b6c"
down_revision: Union[str, Sequence[str], None] = "6c8d0e2f4a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_prospecting_searches",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("offer_key", sa.String(64), nullable=True),
        sa.Column("filters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("schedule", sa.String(64), nullable=False, server_default="manual"),
        sa.Column("notification_policy", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_saved_searches_org_enabled", "saved_prospecting_searches", ["organization_id", "enabled"])

    op.create_table(
        "prospecting_alerts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("saved_search_id", sa.UUID(), sa.ForeignKey("saved_prospecting_searches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("lead_id", sa.UUID(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=True),
        sa.Column("event_id", sa.UUID(), sa.ForeignKey("event_opportunities.id", ondelete="CASCADE"), nullable=True),
        sa.Column("kind", sa.String(48), nullable=False, server_default="saved_search_match"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "fingerprint", name="uq_prospecting_alerts_org_fingerprint"),
    )
    op.create_index("ix_prospecting_alerts_org_status_created", "prospecting_alerts", ["organization_id", "status", "created_at"])

    op.create_table(
        "event_series",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("series_key", sa.String(180), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("family", sa.String(64), nullable=True),
        sa.Column("recurrence_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("previous_event_id", sa.UUID(), sa.ForeignKey("event_opportunities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("latest_event_id", sa.UUID(), sa.ForeignKey("event_opportunities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expected_next_window", postgresql.JSONB(), nullable=True),
        sa.Column("series_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "series_key", name="uq_event_series_org_key"),
    )
    op.create_index("ix_event_series_org_window", "event_series", ["organization_id", "updated_at"])

    op.create_table(
        "case_studies",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("offer_key", sa.String(64), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("segments", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("problem", sa.Text(), nullable=False),
        sa.Column("solution", sa.Text(), nullable=False),
        sa.Column("proof", sa.Text(), nullable=True),
        sa.Column("assets", postgresql.JSONB(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_case_studies_org_offer_active", "case_studies", ["organization_id", "offer_key", "active"])

    op.create_table(
        "prospecting_agent_states",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", sa.UUID(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="DISCOVERED"),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column("history", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "lead_id", name="uq_agent_state_org_lead"),
    )
    op.create_index("ix_agent_state_org_state", "prospecting_agent_states", ["organization_id", "state"])


def downgrade() -> None:
    op.drop_index("ix_agent_state_org_state", table_name="prospecting_agent_states")
    op.drop_table("prospecting_agent_states")
    op.drop_index("ix_case_studies_org_offer_active", table_name="case_studies")
    op.drop_table("case_studies")
    op.drop_index("ix_event_series_org_window", table_name="event_series")
    op.drop_table("event_series")
    op.drop_index("ix_prospecting_alerts_org_status_created", table_name="prospecting_alerts")
    op.drop_table("prospecting_alerts")
    op.drop_index("ix_saved_searches_org_enabled", table_name="saved_prospecting_searches")
    op.drop_table("saved_prospecting_searches")
