"""add correlation and campaign scope to provider execution metrics

Revision ID: ee5f6b7c8d0a
Revises: dd9e0f1a2b3c
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "ee5f6b7c8d0a"
down_revision: Union[str, Sequence[str], None] = "dd9e0f1a2b3c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {
        column["name"] for column in inspector.get_columns("provider_execution_metrics")
    }
    if "correlation_id" not in columns:
        op.add_column(
            "provider_execution_metrics",
            sa.Column("correlation_id", sa.UUID(), nullable=True),
        )
    if "campaign_id" not in columns:
        op.add_column(
            "provider_execution_metrics",
            sa.Column(
                "campaign_id",
                sa.UUID(),
                sa.ForeignKey("campaigns.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    if "usage" not in columns:
        op.add_column(
            "provider_execution_metrics",
            sa.Column("usage", postgresql.JSONB(), nullable=True),
        )
    try:
        op.create_index(
            "ix_provider_execution_metrics_correlation",
            "provider_execution_metrics",
            ["correlation_id"],
        )
    except sa.exc.InternalError:
        ...  # índice já existe (migration parcialmente aplicada)


def downgrade() -> None:
    op.drop_index(
        "ix_provider_execution_metrics_correlation",
        table_name="provider_execution_metrics",
    )
    op.drop_constraint(
        "provider_execution_metrics_campaign_id_fkey",
        "provider_execution_metrics",
        type_="foreignkey",
    )
    op.drop_column("provider_execution_metrics", "campaign_id")
    op.drop_column("provider_execution_metrics", "correlation_id")
    op.drop_column("provider_execution_metrics", "usage")