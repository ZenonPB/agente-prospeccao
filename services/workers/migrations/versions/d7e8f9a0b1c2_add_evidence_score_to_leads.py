"""add evidence_score to leads (Fase 3)

Revision ID: d7e8f9a0b1c2
Revises: d6e7f8a9b0c1
Create Date: 2026-09-04

Coluna additive-only: guarda outputs estruturados dos serviços semânticos da
Fase 3 (chain_detection, intent_engine, buying_trigger, decision_maker_strategy,
prospecting_hypothesis, universal_questions). Não substitui `score_vector` —
apenas adiciona inferências derivadas, todas com fonte rastreável.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, Sequence[str], None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'leads',
        sa.Column('evidence_score', JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('leads', 'evidence_score')
