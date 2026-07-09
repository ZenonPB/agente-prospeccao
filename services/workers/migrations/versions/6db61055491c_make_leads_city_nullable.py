"""Make leads city nullable

Revision ID: 6db61055491c
Revises: b70743466f89
Create Date: 2026-07-08 22:35:08.000311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6db61055491c'
down_revision: Union[str, Sequence[str], None] = 'b70743466f89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('leads', 'city', nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('leads', 'city', nullable=False)
