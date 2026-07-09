"""add analysis_profile to campaigns

Revision ID: 90f2b8f9d66e
Revises: 6db61055491c
Create Date: 2026-07-09 01:15:21.094168

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '90f2b8f9d66e'
down_revision: Union[str, Sequence[str], None] = '6db61055491c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    analysis_profile_enum = sa.Enum(
        'web_presence', 'business_opportunity',
        name='analysis_profile',
    )
    analysis_profile_enum.create(op.get_bind(), checkfirst=True)

    op.add_column('campaigns', sa.Column(
        'analysis_profile',
        sa.Enum('web_presence', 'business_opportunity', name='analysis_profile', create_type=False),
        nullable=False,
        server_default='web_presence',
    ))


def downgrade() -> None:
    op.drop_column('campaigns', 'analysis_profile')
    sa.Enum(name='analysis_profile').drop(op.get_bind(), checkfirst=True)
