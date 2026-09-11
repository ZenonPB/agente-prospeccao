"""Persist proposals for controlled commercial learning.

Revision ID: 3b6c8d0e1f2a
Revises: b2c3d4e5f6a8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "3b6c8d0e1f2a"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = "fe4f5a6b7c8d"


def upgrade() -> None:
    op.execute("ALTER TYPE org_audit_event ADD VALUE IF NOT EXISTS 'CONTROLLED_LEARNING_PROPOSED'")
    op.create_table(
        "controlled_learning_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_comparison_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offer_key", sa.String(length=64), nullable=False),
        sa.Column("proposal_version", sa.Integer(), nullable=False),
        sa.Column("approved_version", sa.String(length=32), nullable=False),
        sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="PROPOSED", nullable=False),
        sa.Column("evidence_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("published_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_comparison_id"], ["commercial_comparisons.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["published_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "source_comparison_id", name="uq_controlled_learning_org_comparison"),
        sa.UniqueConstraint(
            "organization_id", "offer_key", "proposal_version",
            name="uq_controlled_learning_org_offer_version",
        ),
    )
    op.create_index(
        "ix_controlled_learning_org_offer_status",
        "controlled_learning_proposals",
        ["organization_id", "offer_key", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_controlled_learning_org_offer_status",
        table_name="controlled_learning_proposals",
    )
    op.drop_table("controlled_learning_proposals")