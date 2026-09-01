"""scoring feedbacks — feedback humano sobre o score da IA

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
Create Date: 2026-09-01

Insumo do loop de aprendizado (docs/ai-feedback-loop.md): o consultor
discorda do score dado pela IA a um lead; os feedbacks acumulados por
template/organização serão compilados em regras de calibração (Fase 2).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c3d4e5f6a7b9'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DIRECTIONS = ('MUITO_ALTO', 'MUITO_BAIXO')
_STATUSES = ('PENDING', 'APPLIED', 'DISMISSED')


def upgrade() -> None:
    direction = postgresql.ENUM(
        *_DIRECTIONS, name='feedback_direction', create_type=True
    )
    status = postgresql.ENUM(
        *_STATUSES, name='feedback_status', create_type=True
    )
    op.create_table(
        'scoring_feedbacks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('leads.id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id'), nullable=True),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('campaigns.id'), nullable=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('campaign_scoring_templates.id'), nullable=True),
        sa.Column('original_score', sa.Integer(), nullable=False),
        sa.Column('suggested_score', sa.Integer(), nullable=False),
        sa.Column('direction', direction, nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', status, nullable=False, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_scoring_feedbacks_org_status', 'scoring_feedbacks',
        ['organization_id', 'status'],
    )
    op.create_index(
        'ix_scoring_feedbacks_lead_id', 'scoring_feedbacks', ['lead_id'],
    )
    op.create_index(
        'ix_scoring_feedbacks_template_id', 'scoring_feedbacks', ['template_id'],
    )
    # Action na trilha de atividades (enum existente ganha novo valor).
    op.execute(
        "ALTER TYPE lead_activity_action ADD VALUE IF NOT EXISTS 'SCORE_FEEDBACK'"
    )


def downgrade() -> None:
    op.drop_index('ix_scoring_feedbacks_template_id', table_name='scoring_feedbacks')
    op.drop_index('ix_scoring_feedbacks_lead_id', table_name='scoring_feedbacks')
    op.drop_index('ix_scoring_feedbacks_org_status', table_name='scoring_feedbacks')
    op.drop_table('scoring_feedbacks')
    op.execute('DROP TYPE IF EXISTS feedback_direction')
    op.execute('DROP TYPE IF EXISTS feedback_status')
