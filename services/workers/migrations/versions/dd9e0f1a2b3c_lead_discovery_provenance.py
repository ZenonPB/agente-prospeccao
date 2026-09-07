"""persist normalized discovery provenance on leads

Revision ID: dd9e0f1a2b3c
Revises: cc8d9e0f1a2b
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "dd9e0f1a2b3c"
down_revision: Union[str, Sequence[str], None] = "cc8d9e0f1a2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("leads")}
    if "discovery_provenance" not in columns:
        op.add_column("leads", sa.Column("discovery_provenance", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "discovery_provenance")