"""Cria snapshots imutáveis de resolução de decisores."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "2f7a9b1c3d5e"
down_revision: Union[str, Sequence[str], None] = "2e6f8a0c2d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "decision_resolution_snapshots" in inspector.get_table_names():
        # Alguns ambientes de desenvolvimento já criaram o schema via
        # ``Base.metadata.create_all``. A migration continua idempotente e
        # apenas registra a revisão nesse caso.
        return
    op.create_table(
        "decision_resolution_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.String(length=32), server_default="enrichment", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lead_id", "snapshot_hash", name="uq_decision_resolution_snapshot_hash"),
    )
    op.create_index(
        "ix_decision_resolution_snapshots_org_lead",
        "decision_resolution_snapshots",
        ["organization_id", "lead_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_decision_resolution_snapshots_org_lead", table_name="decision_resolution_snapshots")
    op.drop_table("decision_resolution_snapshots")