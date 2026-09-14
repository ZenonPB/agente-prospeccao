"""Garante timestamp de versão para concorrência otimista em leads."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "f1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backfill determinístico: preserva a criação quando disponível e usa o
    # relógio do banco somente para registros legados sem created_at.
    op.execute(
        "UPDATE leads "
        "SET updated_at = COALESCE(created_at, now()) "
        "WHERE updated_at IS NULL"
    )
    op.alter_column(
        "leads",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    # O backfill é compatível e não deve ser desfeito; apenas remove o default
    # para permitir rollback da mudança de schema sem apagar histórico.
    op.alter_column(
        "leads",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
    )
