"""enrichment_strategy — estratégia declarada de execução do enriquecimento

Revision ID: c5d6e7f8a9b0
Revises: f1a2b3c4d5e6
Create Date: 2026-09-04

Coluna additive-only em campaign_scoring_templates: skip de capabilities e
parada antecipada declaradas pela oferta (docs/melhorias/08). NULL mantém o
comportamento atual (executa tudo ativo em enrichment_steps).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'campaign_scoring_templates',
        sa.Column('enrichment_strategy', JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('campaign_scoring_templates', 'enrichment_strategy')
