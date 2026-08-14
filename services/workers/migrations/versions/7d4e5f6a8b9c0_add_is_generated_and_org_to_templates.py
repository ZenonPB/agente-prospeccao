"""add is_generated and organization_id to scoring templates

Revision ID: 7d4e5f6a8b9c0
Revises: 6b3c2a1d9e8f4
Create Date: 2026-08-01

Geração de template sob demanda:
- `campaign_scoring_templates.is_generated` (bool, default false) — distingue
  templates criados por IA dos seeds manuais.
- `campaign_scoring_templates.organization_id` (FK organizations, nullable) —
  templates gerados são por org (NULL = global/seed).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = '7d4e5f6a8b9c0'
down_revision: Union[str, Sequence[str], None] = '6b3c2a1d9e8f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'campaign_scoring_templates',
        sa.Column('is_generated', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.add_column(
        'campaign_scoring_templates',
        sa.Column('organization_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id'), nullable=True),
    )
    op.create_index('ix_campaign_scoring_templates_organization_id',
                    'campaign_scoring_templates', ['organization_id'])


def downgrade() -> None:
    op.drop_index('ix_campaign_scoring_templates_organization_id',
                  table_name='campaign_scoring_templates')
    op.drop_column('campaign_scoring_templates', 'organization_id')
    op.drop_column('campaign_scoring_templates', 'is_generated')
