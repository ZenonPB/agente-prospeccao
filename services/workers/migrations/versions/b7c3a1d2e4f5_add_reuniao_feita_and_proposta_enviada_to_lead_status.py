"""add REUNIAO_FEITA and PROPOSTA_ENVIADA to lead_status enum

Revision ID: b7c3a1d2e4f5
Revises: 90f2b8f9d66e
Create Date: 2026-07-09 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = 'b7c3a1d2e4f5'
down_revision: Union[str, Sequence[str], None] = '90f2b8f9d66e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE lead_status ADD VALUE 'REUNIAO_FEITA'")
    op.execute("ALTER TYPE lead_status ADD VALUE 'PROPOSTA_ENVIADA'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type.
    # To downgrade, one would need to create a new type and migrate data.
    pass
