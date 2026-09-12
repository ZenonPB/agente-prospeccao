"""add inbound token hash per organization

Revision ID: 5b7c9d1e3f4a
Revises: 4a6b8c9d1e2f
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "5b7c9d1e3f4a"
down_revision: Union[str, Sequence[str], None] = "4a6b8c9d1e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("inbound_token_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "uq_organizations_inbound_token_hash",
        "organizations",
        ["inbound_token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_organizations_inbound_token_hash", table_name="organizations")
    op.drop_column("organizations", "inbound_token_hash")
