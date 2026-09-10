"""Persist the matcher score breakdown on current opportunities.

Revision ID: 3d8e0f2a3b4c
Revises: 3c7d9e1f2a3b
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "3d8e0f2a3b4c"
down_revision: Union[str, Sequence[str], None] = "3c7d9e1f2a3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lead_opportunities",
        sa.Column("score_breakdown", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lead_opportunities", "score_breakdown")