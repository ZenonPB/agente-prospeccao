"""template learning — regras de calibração aprendidas com o time

Revision ID: d8e9f0a1b2c3
Revises: c3d4e5f6a7b9
Create Date: 2026-09-01

Fase 2 do loop de aprendizado (docs/ai-feedback-loop.md): feedbacks de score
acumulados por template/organização são compilados pela LLM em regras
objetivas, armazenadas em `template_learning` e injetadas no prompt de
scoring. Feedbacks já compilados viram COMPILED.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'template_learning',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('campaign_scoring_templates.id'), nullable=False),
        sa.Column('instructions', postgresql.JSONB(), nullable=False),
        sa.Column('compiled_from', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        'ix_template_learning_org_template', 'template_learning',
        ['organization_id', 'template_id'],
    )
    # Status extra: feedback já consumido por uma compilação.
    op.execute(
        "ALTER TYPE feedback_status ADD VALUE IF NOT EXISTS 'COMPILED'"
    )


def downgrade() -> None:
    op.drop_index('ix_template_learning_org_template', table_name='template_learning')
    op.drop_table('template_learning')
