"""add enrichment_timestamps to leads

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Timestamps por fonte do enriquecimento ({"linkedin", "site", "reviews"})
    # em ISO — alimenta o TTL (não re-buscar dentro dele) e a UI de dados antigos.
    op.add_column('leads', sa.Column('enrichment_timestamps', JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'enrichment_timestamps')