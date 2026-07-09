"""add pitch_angle and suggested_subject to leads

Revision ID: 1fb286c0715b
Revises: b7c3a1d2e4f5
Create Date: 2026-07-09 02:05:31.880839

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1fb286c0715b'
down_revision: Union[str, Sequence[str], None] = 'b7c3a1d2e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('leads', sa.Column('pitch_angle', sa.Text(), nullable=True))
    op.add_column('leads', sa.Column('suggested_subject', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('leads', 'suggested_subject')
    op.drop_column('leads', 'pitch_angle')
