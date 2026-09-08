"""create company_aliases table for cross-provider identity resolution

Revision ID: ff8a9b0c1d2e
Revises: ee5f6b7c8d0a
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ff8a9b0c1d2e"
down_revision: Union[str, Sequence[str], None] = "ee5f6b7c8d0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "company_aliases" in inspector.get_table_names():
        return  # tabela já existente (migration parcialmente aplicada)

    op.create_table(
        "company_aliases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("alias_kind", sa.String(length=50), nullable=False),
        sa.Column("alias_value", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "alias_kind",
            "alias_value",
            name="uq_company_aliases_org_kind_value",
        ),
    )
    op.create_index(
        "ix_company_aliases_company",
        "company_aliases",
        ["company_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "company_aliases" not in inspector.get_table_names():
        return

    op.drop_index("ix_company_aliases_company", table_name="company_aliases")
    op.drop_table("company_aliases")