"""add PROPOSAL_SENT and LOST outcome actions to activity enum

Revision ID: f3a4b5c6d7e8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-03

Fase 3.6 (feedback conversão -> score):
- Novos valores `PROPOSAL_SENT` e `LOST` no enum `lead_activity_action` (trilha).
  Permitem registrar o outcome comercial ao marcar PROPOSTA_ENVIADA / PERDIDO.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE lead_activity_action ADD VALUE IF NOT EXISTS 'PROPOSAL_SENT'")
    op.execute("ALTER TYPE lead_activity_action ADD VALUE IF NOT EXISTS 'LOST'")


def downgrade() -> None:
    # PostgreSQL não suporta remover valores de um tipo enum; para reverter,
    # seria necessário criar um novo tipo e migrar os dados.
    pass