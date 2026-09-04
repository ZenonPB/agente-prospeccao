"""prescoring_discards — auditoria de candidatos descartados pelo gate

Revision ID: f1a2b3c4d5e6
Revises: a7b8c9d0e1f2
Create Date: 2026-09-04

Os descartes do pre-scoring eram voláteis (só log): sem registro não há
revisão humana de falsos-negativos nem recalibração de threshold. Tabela
additive-only, upsert idempotente por (campaign_id, place_id).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'prescoring_discards',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id'), nullable=True),
        sa.Column('campaign_id', UUID(as_uuid=True),
                  sa.ForeignKey('campaigns.id'), nullable=True),
        sa.Column('job_id', UUID(as_uuid=True), nullable=True),
        sa.Column('place_id', sa.String(255), nullable=True),
        sa.Column('company_name', sa.String(255)),
        sa.Column('candidate_data', JSONB),
        sa.Column('signals', JSONB),
        sa.Column('discovery_score', sa.Integer),
        sa.Column('threshold', sa.Integer),
        sa.Column('profile_key', sa.String(50)),
        sa.Column('reason', sa.String(30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('campaign_id', 'place_id',
                            name='uq_prescoring_discards_campaign_place'),
    )
    op.create_index('ix_prescoring_discards_org_created',
                    'prescoring_discards', ['organization_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_prescoring_discards_org_created', table_name='prescoring_discards')
    op.drop_table('prescoring_discards')