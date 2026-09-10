"""Cria histórico append-only de oportunidades e vínculo de snapshot em vendas."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "3a5b7c9d1e2f"
down_revision: Union[str, Sequence[str], None] = "2f7a9b1c3d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "lead_opportunity_snapshots" not in tables:
        op.create_table(
            "lead_opportunity_snapshots",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("organization_id", sa.UUID(), nullable=False),
            sa.Column("lead_id", sa.UUID(), nullable=False),
            sa.Column("lead_opportunity_id", sa.UUID(), nullable=True),
            sa.Column("offer_key", sa.String(length=64), nullable=False),
            sa.Column("offer_version", sa.String(length=32), nullable=True),
            sa.Column("formula_version", sa.String(length=32), server_default="matcher-v1", nullable=False),
            sa.Column("profile_snapshot_hash", sa.String(length=64), nullable=True),
            sa.Column("score", sa.Integer(), server_default="0", nullable=False),
            sa.Column("signals_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("evidence_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
            sa.Column("reason", sa.String(length=32), server_default="enrichment", nullable=False),
            sa.Column("scored_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["lead_opportunity_id"], ["lead_opportunities.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("lead_id", "snapshot_hash", name="uq_lead_opportunity_snapshot_hash"),
        )
        op.create_index(
            "ix_lead_opportunity_snapshots_org_lead",
            "lead_opportunity_snapshots",
            ["organization_id", "lead_id", "created_at"],
        )

    for table in ("commercial_outcomes", "conversions"):
        columns = {col["name"] for col in inspector.get_columns(table)}
        if "lead_opportunity_snapshot_id" not in columns:
            op.add_column(
                table,
                sa.Column("lead_opportunity_snapshot_id", sa.UUID(), nullable=True),
            )
            op.create_foreign_key(
                f"fk_{table}_opportunity_snapshot",
                table,
                "lead_opportunity_snapshots",
                ["lead_opportunity_snapshot_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    for table in ("conversions", "commercial_outcomes"):
        bind = op.get_bind()
        inspector = sa.inspect(bind)
        columns = {col["name"] for col in inspector.get_columns(table)}
        if "lead_opportunity_snapshot_id" in columns:
            try:
                op.drop_constraint(f"fk_{table}_opportunity_snapshot", table, type_="foreignkey")
            except Exception:
                pass
            op.drop_column(table, "lead_opportunity_snapshot_id")
    op.drop_index("ix_lead_opportunity_snapshots_org_lead", table_name="lead_opportunity_snapshots")
    op.drop_table("lead_opportunity_snapshots")
