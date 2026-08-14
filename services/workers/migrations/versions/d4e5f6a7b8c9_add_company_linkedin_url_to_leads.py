"""add company_linkedin_url to leads

Revision ID: d4e5f6a7b8c9
Revises: bff05fb7eb01
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'bff05fb7eb01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Página da empresa no LinkedIn, localizada por busca passiva no
    # enriquecimento (linkedin.com/company/<slug>).
    op.add_column('leads', sa.Column('company_linkedin_url', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'company_linkedin_url')