"""add offer version to lead opportunities

Revision ID: fc2d3e4f5a6b
Revises: fb1c2d3e4f5a
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "fc2d3e4f5a6b"
down_revision: Union[str, Sequence[str], None] = "fb1c2d3e4f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lead_opportunities", sa.Column("offer_version", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("lead_opportunities", "offer_version")