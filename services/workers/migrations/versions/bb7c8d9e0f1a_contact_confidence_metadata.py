"""persist evidence-based contact identity and source confidence

Revision ID: bb7c8d9e0f1a
Revises: aa6b7c8d9e0f
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "bb7c8d9e0f1a"
down_revision: Union[str, Sequence[str], None] = "aa6b7c8d9e0f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("contacts")}
    definitions = (
        sa.Column("identity_confidence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("contact_confidence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source_reliability", sa.Float(), server_default="0", nullable=False),
        sa.Column("verification_status", sa.String(length=40), server_default="needs_review", nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in definitions:
        if column.name not in columns:
            op.add_column("contacts", column)


def downgrade() -> None:
    op.drop_column("contacts", "last_verified_at")
    op.drop_column("contacts", "verification_status")
    op.drop_column("contacts", "source_reliability")
    op.drop_column("contacts", "contact_confidence")
    op.drop_column("contacts", "identity_confidence")