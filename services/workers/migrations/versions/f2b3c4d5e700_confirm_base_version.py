"""Guarda a identidade da confirmacao idempotente do Historical Importer.

Revision ID: f2b3c4d5e700
Revises: d2e3f4a5b6c7

A confirmacao vencedora precisa registrar de qual expected_version partiu e
qual transacao a efetivou. O retry posterior com a mesma chave e a mesma
versao original so e reconhecido como replay idempotente quando a
confirmacao ja estava visivel no snapshot MVCC de abertura do retry; os
concorrentes perdedores da mesma corrida (mesma chave, mesma versao-base,
confirmacao ainda nao visivel) continuam recebendo VERSION_CONFLICT. As
colunas sao aditivas e anulaveis: bancos ja migrados nao exigem backfill
(NULL = confirmacao anterior ao contrato).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2b3c4d5e700"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "import_jobs",
        sa.Column("confirm_base_version", sa.Integer(), nullable=True),
    )
    op.add_column(
        "import_jobs",
        sa.Column("confirm_xid", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("import_jobs", "confirm_xid")
    op.drop_column("import_jobs", "confirm_base_version")
