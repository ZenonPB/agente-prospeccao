"""Alinha lead_activity_action com o enum usado pelo runtime.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-09-13

`NEGOTIATION_UPDATED` já existia no modelo e era usado por rotas comerciais,
mas nunca havia sido adicionado ao enum PostgreSQL. Isso fazia a escrita falhar
somente em banco real. A migration é intencionalmente idempotente.
"""
from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE lead_activity_action ADD VALUE IF NOT EXISTS 'NEGOTIATION_UPDATED'"
    )


def downgrade() -> None:
    # PostgreSQL não permite remover com segurança um único valor de enum sem
    # recriar o tipo/tabela. Downgrade destrutivo aqui seria pior que manter um
    # valor compatível e não utilizado.
    pass
