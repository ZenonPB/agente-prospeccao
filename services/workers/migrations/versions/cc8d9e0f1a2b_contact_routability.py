"""persist contact routability classification

Revision ID: cc8d9e0f1a2b
Revises: bb7c8d9e0f1a
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cc8d9e0f1a2b"
down_revision: Union[str, Sequence[str], None] = "bb7c8d9e0f1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("contacts")}
    definitions = (
        sa.Column("routability_type", sa.String(length=24), server_default="UNKNOWN", nullable=False),
        sa.Column("routable", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("routability_reason", sa.String(length=80), nullable=True),
    )
    for column in definitions:
        if column.name not in columns:
            op.add_column("contacts", column)


def downgrade() -> None:
    op.drop_column("contacts", "routability_reason")
    op.drop_column("contacts", "routable")
    op.drop_column("contacts", "routability_type")