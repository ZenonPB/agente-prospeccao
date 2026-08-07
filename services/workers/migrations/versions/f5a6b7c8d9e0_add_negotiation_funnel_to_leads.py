"""add negotiation funnel (stage + contract outcome) to leads

Revision ID: f5a6b7c8d9e0
Revises: f4a5b6c7d8e9
Create Date: 2026-08-06

Roadmap-leads C.3 — funil de negociação para largar a planilha Alphamec:
- `leads.negotiation_stage` (enum `negotiation_stage`: RD/ORÇAMENTO/RP) — o
  estágio interno de negociação entre o lead responder e o fechamento.
- `leads.contract_outcome` (enum `contract_outcome`: APROVADO/REPROVADO/
  EM_ANALISE) — o resultado do contrato final.
- `leads.outcome_date` — quando a etapa/resultado foi marcado.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

negotiation_stage_enum = postgresql.ENUM(
    'RD', 'ORCAMENTO', 'RP',
    name='negotiation_stage', create_type=False,
)

contract_outcome_enum = postgresql.ENUM(
    'APROVADO', 'REPROVADO', 'EM_ANALISE',
    name='contract_outcome', create_type=False,
)

revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, Sequence[str], None] = 'f4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    negotiation_stage_enum.create(op.get_bind(), checkfirst=True)
    contract_outcome_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('leads', sa.Column('negotiation_stage', negotiation_stage_enum, nullable=True))
    op.add_column('leads', sa.Column('contract_outcome', contract_outcome_enum, nullable=True))
    op.add_column('leads', sa.Column('outcome_date', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'outcome_date')
    op.drop_column('leads', 'contract_outcome')
    op.drop_column('leads', 'negotiation_stage')
    contract_outcome_enum.drop(op.get_bind(), checkfirst=True)
    negotiation_stage_enum.drop(op.get_bind(), checkfirst=True)