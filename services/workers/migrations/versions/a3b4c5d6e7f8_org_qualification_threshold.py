"""qualification_threshold por organização

Revision ID: a3b4c5d6e7f8
Revises: e6f7a8b9c0d1
Create Date: 2026-08-14

Cada organização pode calibrar o limiar QUALIFICADO/DESQUALIFICADO
conforme o histórico de conversões. Default 60 (mantém compatibilidade
com o hardcoded anterior). Apenas owner/admin podem alterar via PATCH
em `/api/orgs/{id}`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'organizations',
        sa.Column(
            'qualification_threshold',
            sa.Integer(),
            nullable=False,
            server_default='60',
        ),
    )


def downgrade() -> None:
    op.drop_column('organizations', 'qualification_threshold')
