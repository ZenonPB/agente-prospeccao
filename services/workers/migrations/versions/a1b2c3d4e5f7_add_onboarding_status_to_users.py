"""add_onboarding_status_to_users

Revision ID: a1b2c3d4e5f7
Revises: 2b137f2dc6f5
Create Date: 2026-08-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = '2b137f2dc6f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    onboarding_enum = postgresql.ENUM('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'DISMISSED', name='onboarding_status')
    onboarding_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'users',
        sa.Column(
            'onboarding_status',
            sa.Enum('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'DISMISSED', name='onboarding_status'),
            server_default='NOT_STARTED',
            nullable=False
        )
    )


def downgrade() -> None:
    op.drop_column('users', 'onboarding_status')
    onboarding_enum = postgresql.ENUM('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', 'DISMISSED', name='onboarding_status')
    onboarding_enum.drop(op.get_bind(), checkfirst=True)
