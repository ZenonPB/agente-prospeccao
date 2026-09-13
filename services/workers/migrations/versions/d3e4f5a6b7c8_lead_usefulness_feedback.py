"""Feedback de utilidade do lead (util / nao util) com motivo fechado.

Revision ID: d3e4f5a6b7c8
Revises: c2d4e6f8a0b1
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c2d4e6f8a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_REASONS = (
    "EMPRESA_ERRADA",
    "SEM_NECESSIDADE",
    "CONTATO_ERRADO",
    "FORA_DO_PORTE",
    "FORA_DA_REGIAO",
    "JA_TEM_FORNECEDOR",
    "DADOS_INCORRETOS",
    "OUTRO",
)


def upgrade() -> None:
    # O enum pode já existir se uma tentativa anterior falhou após criá-lo
    # (DDL transacional parcial). Cria só se necessário e desabilita a
    # segunda tentativa automática durante `create_table`.
    reason = postgresql.ENUM(*_REASONS, name="lead_usefulness_reason")
    reason.create(op.get_bind(), checkfirst=True)
    reason_for_column = postgresql.ENUM(
        *_REASONS, name="lead_usefulness_reason", create_type=False
    )
    op.create_table(
        "lead_usefulness_feedbacks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=True),
        sa.Column("useful", sa.Boolean(), nullable=False),
        sa.Column("reason", reason_for_column, nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("lead_id", "user_id", name="uq_lead_usefulness_lead_user"),
    )
    op.create_index("ix_lead_usefulness_org_created", "lead_usefulness_feedbacks", ["organization_id", "created_at"])
    op.create_index("ix_lead_usefulness_lead_id", "lead_usefulness_feedbacks", ["lead_id"])
    op.execute("ALTER TYPE lead_activity_action ADD VALUE IF NOT EXISTS 'LEAD_FEEDBACK'")


def downgrade() -> None:
    op.drop_index("ix_lead_usefulness_lead_id", table_name="lead_usefulness_feedbacks")
    op.drop_index("ix_lead_usefulness_org_created", table_name="lead_usefulness_feedbacks")
    op.drop_table("lead_usefulness_feedbacks")
    postgresql.ENUM(name="lead_usefulness_reason").drop(op.get_bind(), checkfirst=True)
