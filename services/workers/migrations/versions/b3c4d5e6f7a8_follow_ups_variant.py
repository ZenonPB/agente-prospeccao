"""variant por etapa da cadência (A/B de mensagens)

Revision ID: b3c4d5e6f7a8
Revises: a3b4c5d6e7f8
Create Date: 2026-08-14

Cada `FollowUp` pode carregar um rótulo de variante (ex.: "A"/"B"). Quando o
consultor gera mensagens A/B pelo frontend, escolhe uma variante por etapa
e a marca antes de enviar — o scheduler e a medição de resposta usam esse
rótulo para calcular desempenho por variante.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'follow_ups',
        sa.Column('variant', sa.String(length=32), nullable=True),
    )
    op.create_index(
        'ix_follow_ups_org_variant', 'follow_ups',
        ['lead_id', 'variant'], unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_follow_ups_org_variant', table_name='follow_ups')
    op.drop_column('follow_ups', 'variant')
