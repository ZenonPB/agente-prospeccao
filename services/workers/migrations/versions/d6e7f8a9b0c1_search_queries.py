"""search_queries — busca multi-query por campanha

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-09-04

Coluna additive-only em campaigns: lista de consultas Places para cobertura
por variedade semântica (docs/melhorias/04). NULL mantém o fluxo atual
(places_query único).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'd6e7f8a9b0c1'
down_revision: Union[str, Sequence[str], None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('campaigns', sa.Column('search_queries', JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('campaigns', 'search_queries')
