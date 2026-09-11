"""Alinha o default de formula_version com o runtime (matcher-v2).

Revision ID: 4a6b8c9d1e2f
Revises: a4b5c6d7e8f9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4a6b8c9d1e2f"
down_revision: Union[str, Sequence[str], None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "lead_opportunity_snapshots",
        "formula_version",
        existing_type=sa.String(length=32),
        server_default="matcher-v2",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "lead_opportunity_snapshots",
        "formula_version",
        existing_type=sa.String(length=32),
        server_default="matcher-v1",
        existing_nullable=False,
    )
