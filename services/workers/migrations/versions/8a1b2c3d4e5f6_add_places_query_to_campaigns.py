"""add places_query to campaigns

Revision ID: 8a1b2c3d4e5f6
Revises: 7d4e5f6a8b9c0
Create Date: 2026-08-01

Item 1.4 (campanha por linguagem natural):
- `campaigns.places_query` (varchar 255, nullable) — query otimizada para o
  Google Places sugerida pelo agente. Quando presente, o pipeline usa esta
  query em vez de montar uma automaticamente a partir de
  target_segment/target_city/target_state.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7d4e5f6a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('campaigns', sa.Column('places_query', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('campaigns', 'places_query')
