"""add linkedin fields to contacts and CONTACT_ENRICHED activity

Revision ID: e1f2a3b4c5d6
Revises: c3d4e5f6a7b8c
Create Date: 2026-08-05

Fase 3.4 (contato de decisor email + LinkedIn):
- `contacts.linkedin_url` (String 255, nullable) — URL do perfil LinkedIn do decisor.
- `contacts.linkedin_confidence` (Integer, default 0) — confiança 0-100 do perfil.
- Novo valor `CONTACT_ENRICHED` no enum `lead_activity_action` (trilha).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'contacts',
        sa.Column('linkedin_url', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'contacts',
        sa.Column('linkedin_confidence', sa.Integer(), nullable=False,
                  server_default='0'),
    )
    op.execute("ALTER TYPE lead_activity_action ADD VALUE 'CONTACT_ENRICHED'")


def downgrade() -> None:
    # PostgreSQL não suporta remover valores de um tipo enum; para reverter,
    # seria necessário criar um novo tipo e migrar os dados.
    op.drop_column('contacts', 'linkedin_confidence')
    op.drop_column('contacts', 'linkedin_url')
