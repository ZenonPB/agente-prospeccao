"""add enrichment_steps, cadence_schedule and raw_business_data

Revision ID: c2d3e4f5a6b7
Revises: b2c3d4e5f6a9
Create Date: 2026-08-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('campaign_scoring_templates', sa.Column('enrichment_steps', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('campaign_scoring_templates', sa.Column('cadence_schedule', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('enrichments', sa.Column('raw_business_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('enrichments', 'raw_business_data')
    op.drop_column('campaign_scoring_templates', 'cadence_schedule')
    op.drop_column('campaign_scoring_templates', 'enrichment_steps')