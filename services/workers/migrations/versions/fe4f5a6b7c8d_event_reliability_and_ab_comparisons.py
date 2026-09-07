"""persist event provenance/status and auditable A/B comparisons

Revision ID: fe4f5a6b7c8d
Revises: fd3e4f5a6b7c
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "fe4f5a6b7c8d"
down_revision: Union[str, Sequence[str], None] = "fd3e4f5a6b7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    event_columns = {column["name"] for column in inspector.get_columns("event_opportunities")}
    for column in (
        sa.Column("source_identifier", sa.String(255), nullable=True),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("provider_status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("status", sa.String(16), nullable=False, server_default="upcoming"),
        sa.Column("provenance", postgresql.JSONB(), nullable=True),
    ):
        if column.name not in event_columns:
            op.add_column("event_opportunities", column)
    event_indexes = {index["name"] for index in inspector.get_indexes("event_opportunities")}
    if "uq_event_opportunities_org_provider_identifier" not in event_indexes:
        op.create_index(
            "uq_event_opportunities_org_provider_identifier",
            "event_opportunities",
            ["organization_id", "provider", "source_identifier"],
            unique=True,
            postgresql_where=sa.text("source_identifier IS NOT NULL"),
        )

    if "commercial_comparisons" not in inspector.get_table_names():
        op.create_table(
            "commercial_comparisons",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("organization_id", sa.UUID(), nullable=False),
            sa.Column("offer_key", sa.String(64), nullable=False),
            sa.Column("version_a", sa.String(32), nullable=False),
            sa.Column("version_b", sa.String(32), nullable=False),
            sa.Column("result", postgresql.JSONB(), nullable=False),
            sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("approved_version", sa.String(32), nullable=True),
            sa.Column("approved_by_id", sa.UUID(), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approval_evidence", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    comparison_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("commercial_comparisons")}
    if "ix_commercial_comparisons_org_offer" not in comparison_indexes:
        op.create_index(
            "ix_commercial_comparisons_org_offer",
            "commercial_comparisons",
            ["organization_id", "offer_key", "computed_at"],
        )
    op.execute("ALTER TYPE org_audit_event ADD VALUE IF NOT EXISTS 'AB_COMPARISON_APPROVED'")


def downgrade() -> None:
    op.drop_index("ix_commercial_comparisons_org_offer", table_name="commercial_comparisons")
    op.drop_table("commercial_comparisons")
    op.drop_index("uq_event_opportunities_org_provider_identifier", table_name="event_opportunities")
    op.drop_column("event_opportunities", "provenance")
    op.drop_column("event_opportunities", "status")
    op.drop_column("event_opportunities", "provider_status")
    op.drop_column("event_opportunities", "provider")
    op.drop_column("event_opportunities", "source_identifier")