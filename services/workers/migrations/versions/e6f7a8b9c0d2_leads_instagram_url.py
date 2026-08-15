"""instagram_url por lead

Revision ID: e6f7a8b9c0d2
Revises: d5e6f7a8b9d0
Create Date: 2026-08-14

Cada lead pode ter um link para o perfil do Instagram do negócio
(`https://instagram.com/<handle>`). Coletado de:
- Places: `websiteUri` cujo host é `instagram.com` (tratado também como
  "sem site próprio" pelo `is_social_domain`).
- Enriquecimento técnico: regex no HTML bruto da página.
- Planilhas CSV (via normalização posterior).

Aparece como fato no scoring (sinal de atividade digital) e no pitch
(link clicável na identidade do lead).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6f7a8b9c0d2'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'leads',
        sa.Column('instagram_url', sa.String(length=255), nullable=True),
    )
    op.create_index(
        'ix_leads_instagram_url', 'leads',
        ['organization_id', 'instagram_url'], unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_leads_instagram_url', table_name='leads')
    op.drop_column('leads', 'instagram_url')
