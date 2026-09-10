"""Revision ID: 2c4e6f8a0d3e
Revises: 2b4d6f8a0c2e

Correção identificada na auditoria do banco (onda 3): a tabela
`follow_up_versions` existe no modelo e é usada pelos endpoints de cadência
(PATCH e GET /cadence/step), mas nenhuma migration a criou — qualquer edição
de etapa quebraria em produção. A tabela é criada com o índice declarado no
modelo.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "2c4e6f8a0d3e"
down_revision: Union[str, Sequence[str], None] = "2b4d6f8a0c2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "follow_up_versions" in inspector.get_table_names():
        return
    op.create_table(
        "follow_up_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "follow_up_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("follow_ups.id"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("variant", sa.String(length=32), nullable=True),
        sa.Column(
            "edited_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("edit_reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_follow_up_versions_follow_up_id",
        "follow_up_versions",
        ["follow_up_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "follow_up_versions" in inspector.get_table_names():
        op.drop_index(
            "ix_follow_up_versions_follow_up_id",
            table_name="follow_up_versions",
        )
        op.drop_table("follow_up_versions")