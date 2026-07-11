"""add contextual scoring templates and explainability fields to leads

Revision ID: c4a1f2e8b9d0
Revises: 1fb286c0715b
Create Date: 2026-07-09 18:00:00.000000

Nesta migration:
- Nova tabela `campaign_scoring_templates` (templates de critérios por serviço)
- FK `campaigns.scoring_template_id`
- Explicabilidade em `leads`: score_factors, evidence, priority,
  priority_reasoning, executive_summary (JSONB/Enum/Text)
- `primary_need` alargado de String(50) para String(255) (deixa de ser
  enum fixo de web — agora categoria contextual livre definida pela IA)

Não altera dados existentes (apenas novos leads serão analisados pelo
pipeline contextual).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = 'c4a1f2e8b9d0'
down_revision: Union[str, Sequence[str], None] = '1fb286c0715b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'campaign_scoring_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('service_label', sa.String(length=255), nullable=False),
        sa.Column('positive_signals', JSONB, nullable=False, server_default='[]'),
        sa.Column('negative_signals', JSONB, nullable=False, server_default='[]'),
        sa.Column('context_signals', JSONB, server_default='[]'),
        sa.Column('requires_technical_report', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('requires_business_data', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('extra_instructions', sa.Text()),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )

    op.add_column(
        'campaigns',
        sa.Column('scoring_template_id', UUID(as_uuid=True),
                   sa.ForeignKey('campaign_scoring_templates.id'), nullable=True),
    )

    op.alter_column('leads', 'primary_need',
                    existing_type=sa.String(length=50),
                    type_=sa.String(length=255),
                    existing_nullable=True)

    op.add_column('leads', sa.Column('score_factors', JSONB, nullable=True))
    op.add_column('leads', sa.Column('evidence', JSONB, nullable=True))

    lead_priority = sa.Enum('HOT', 'WARM', 'COLD', name='lead_priority',
                            create_type=True)
    lead_priority.create(op.get_bind(), checkfirst=False)
    op.add_column('leads', sa.Column('priority', lead_priority, nullable=True))

    op.add_column('leads', sa.Column('priority_reasoning', sa.Text, nullable=True))
    op.add_column('leads', sa.Column('executive_summary', sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'executive_summary')
    op.drop_column('leads', 'priority_reasoning')
    op.drop_column('leads', 'priority')
    sa.Enum(name='lead_priority').drop(op.get_bind(), checkfirst=True)
    op.drop_column('leads', 'evidence')
    op.drop_column('leads', 'score_factors')

    op.alter_column('leads', 'primary_need',
                    existing_type=sa.String(length=255),
                    type_=sa.String(length=50),
                    existing_nullable=True)

    op.drop_column('campaigns', 'scoring_template_id')
    op.drop_table('campaign_scoring_templates')
