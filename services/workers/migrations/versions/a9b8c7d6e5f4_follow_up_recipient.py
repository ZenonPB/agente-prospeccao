"""follow_ups.recipient — destinatário efetivo por etapa

Revision ID: a9b8c7d6e5f4
Revises: c2d3e4f5a6b7
Create Date: 2026-08-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, Sequence[str], None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('follow_ups', sa.Column('recipient', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('follow_ups', 'recipient')
