"""add explicit offer attribution to conversions and outcomes

Revision ID: fd3e4f5a6b7c
Revises: fc2d3e4f5a6b
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "fd3e4f5a6b7c"
down_revision: Union[str, Sequence[str], None] = "fc2d3e4f5a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("commercial_outcomes", sa.Column("lead_opportunity_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_commercial_outcomes_lead_opportunity",
        "commercial_outcomes",
        "lead_opportunities",
        ["lead_opportunity_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("conversions", sa.Column("lead_opportunity_id", sa.UUID(), nullable=True))
    op.add_column("conversions", sa.Column("offer_key", sa.String(64), nullable=True))
    op.add_column("conversions", sa.Column("offer_version", sa.String(32), nullable=True))
    op.create_index("ix_conversions_offer_attribution", "conversions", ["lead_opportunity_id", "offer_key", "offer_version"])
    op.create_foreign_key(
        "fk_conversions_lead_opportunity",
        "conversions",
        "lead_opportunities",
        ["lead_opportunity_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_conversions_lead_opportunity", "conversions", type_="foreignkey")
    op.drop_index("ix_conversions_offer_attribution", table_name="conversions")
    op.drop_column("conversions", "offer_version")
    op.drop_column("conversions", "offer_key")
    op.drop_column("conversions", "lead_opportunity_id")
    op.drop_constraint("fk_commercial_outcomes_lead_opportunity", "commercial_outcomes", type_="foreignkey")
    op.drop_column("commercial_outcomes", "lead_opportunity_id")