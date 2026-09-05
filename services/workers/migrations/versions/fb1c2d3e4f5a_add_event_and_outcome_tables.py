"""add event opportunities and commercial outcomes

Revision ID: fb1c2d3e4f5a
Revises: fa0b1c2d3e4f
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "fb1c2d3e4f5a"
down_revision: Union[str, Sequence[str], None] = "fa0b1c2d3e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "event_opportunities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=True),
        sa.Column("offer_key", sa.String(64), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("organizer", sa.String(255), nullable=True),
        sa.Column("organizer_resolved", postgresql.JSONB(), nullable=True),
        sa.Column("timing", postgresql.JSONB(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("registration_status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "source_url", name="uq_event_opportunities_org_source"),
    )
    op.create_index("ix_event_opportunities_org_date", "event_opportunities", ["organization_id", "event_date"])

    op.create_table(
        "commercial_outcomes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("offer_key", sa.String(64), nullable=False),
        sa.Column("offer_version", sa.String(32), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("value", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("outreach_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("event_key", sa.String(255), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "event_key", name="uq_commercial_outcomes_org_event"),
    )
    op.create_index("ix_commercial_outcomes_org_offer", "commercial_outcomes", ["organization_id", "offer_key", "offer_version"])


def downgrade() -> None:
    op.drop_index("ix_commercial_outcomes_org_offer", table_name="commercial_outcomes")
    op.drop_table("commercial_outcomes")
    op.drop_index("ix_event_opportunities_org_date", table_name="event_opportunities")
    op.drop_table("event_opportunities")