"""Revision ID: 2b4d6f8a0c2e
Revises: 1a2b3c4d5e6f

Provenance consolidada no descarte do pre-scoring: rastreia de onde veio
um candidato rejeitado (providers, consultas, ids) sem abrir candidate_data.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "2b4d6f8a0c2e"
down_revision: Union[str, Sequence[str], None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("prescoring_discards")}
    if "provenance" not in existing:
        op.add_column(
            "prescoring_discards",
            sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("prescoring_discards")}
    if "provenance" in existing:
        op.drop_column("prescoring_discards", "provenance")