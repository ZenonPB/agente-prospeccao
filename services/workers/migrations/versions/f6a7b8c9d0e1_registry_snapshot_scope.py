"""Registra o scope de importação no snapshot do Registry.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0

Coluna aditiva e anulável (`scope` JSONB): snapshots filtrados deixam de
parecer nacionais no ledger, no health e na reprodução histórica. Sem
backfill — snapshots anteriores ao contrato têm scope desconhecido (NULL),
nunca um recorte inventado.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "registry_snapshots",
        sa.Column("scope", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("registry_snapshots", "scope")
