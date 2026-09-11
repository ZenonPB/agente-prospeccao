"""Lockout de login persistente (tabela login_attempts).

O lockout vivia num dict em memória na API — perdido a cada restart e
invisível entre processos. Esta tabela guarda uma linha por e-mail
normalizado (chave primária, sem histórico) com o contador de falhas e o
horizonte do bloqueio.

Revision ID: a4b5c6d7e8f9
Revises: 3d8e0f2a3b4c
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "3d8e0f2a3b4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("email", sa.String(255), primary_key=True),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("login_attempts")
