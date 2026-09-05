"""add declarative offer profile to campaigns

Revision ID: fa0b1c2d3e4f
Revises: f9a0b1c2d3e4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "fa0b1c2d3e4f"
down_revision: Union[str, Sequence[str], None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("campaigns", sa.Column("offer_profile_key", sa.String(length=64), nullable=True))
    op.create_index("ix_campaigns_offer_profile_key", "campaigns", ["offer_profile_key"])


def downgrade() -> None:
    op.drop_index("ix_campaigns_offer_profile_key", table_name="campaigns")
    op.drop_column("campaigns", "offer_profile_key")