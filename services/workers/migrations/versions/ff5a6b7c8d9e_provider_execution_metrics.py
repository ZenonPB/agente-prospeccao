"""persist provider execution telemetry separately from quota counters

Revision ID: ff5a6b7c8d9e
Revises: fe4f5a6b7c8d
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ff5a6b7c8d9e"
down_revision: Union[str, Sequence[str], None] = "fe4f5a6b7c8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "provider_execution_metrics" in inspector.get_table_names():
        return
    op.create_table(
        "provider_execution_metrics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("result_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("budget_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("retryable", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("cost", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provider_execution_metrics_org_recorded",
        "provider_execution_metrics",
        ["organization_id", "recorded_at"],
    )
    op.create_index(
        "ix_provider_execution_metrics_org_provider",
        "provider_execution_metrics",
        ["organization_id", "provider", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_provider_execution_metrics_org_provider", table_name="provider_execution_metrics")
    op.drop_index("ix_provider_execution_metrics_org_recorded", table_name="provider_execution_metrics")
    op.drop_table("provider_execution_metrics")