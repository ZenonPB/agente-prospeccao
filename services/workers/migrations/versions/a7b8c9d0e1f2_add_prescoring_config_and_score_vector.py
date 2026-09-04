"""add prescoring_config aos templates e score_vector aos leads

Revision ID: a7b8c9d0e1f2
Revises: d8e9f0a1b2c3
Create Date: 2026-09-04

Fundação da fase 1 do plano de melhorias (pre-scoring + score vetorial):

- `campaign_scoring_templates.prescoring_config` (JSONB, nullable) — pesos,
  threshold e gate do pre-scoring declarados pela vertical no template;
  sem config, o pipeline mantém o comportamento atual (promove todos).
- `leads.score_vector` (JSONB, nullable) — vetor multidimensional de score
  (need/icp_fit/...) ao lado do `qualification_score` legado, que continua
  sendo a fonte de verdade do funil.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'd8e9f0a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'campaign_scoring_templates',
        sa.Column('prescoring_config', JSONB(), nullable=True),
    )
    op.add_column('leads', sa.Column('score_vector', JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'score_vector')
    op.drop_column('campaign_scoring_templates', 'prescoring_config')
