"""add_linkedin_associated_to_lead_activity_action

Revision ID: c183a77bc662
Revises: c24a13047b0e
Create Date: 2026-08-11 14:17:03.641486

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c183a77bc662'
down_revision: Union[str, Sequence[str], None] = 'c24a13047b0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE lead_activity_action ADD VALUE IF NOT EXISTS 'LINKEDIN_ASSOCIATED'")


def downgrade() -> None:
    pass
