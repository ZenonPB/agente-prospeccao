"""add google rating/reviews to leads

Revision ID: d8e9f0a2b3c4
Revises: c7d8e9f0a1b2
Create Date: 2026-08-05

Reputação no Google como sinal de scoring:
- `leads.google_rating` (Float, nullable) — nota 0–5 da Places API.
- `leads.google_rating_count` (Integer, nullable) — nº de avaliações.
- `leads.google_maps_uri` (String 255, nullable) — link do perfil no Maps.

Negócio mal avaliado / poucas avaliações = oportunidade para serviços;
vira evidência no scoring (extract_business_facts) e no pitch.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8e9f0a2b3c4'
down_revision: Union[str, Sequence[str], None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('google_rating', sa.Float(), nullable=True))
    op.add_column('leads', sa.Column('google_rating_count', sa.Integer(), nullable=True))
    op.add_column('leads', sa.Column('google_maps_uri', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'google_maps_uri')
    op.drop_column('leads', 'google_rating_count')
    op.drop_column('leads', 'google_rating')