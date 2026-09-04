"""create notifications table

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-09-04

Adiciona a persistência das notificações in-app usadas pela API
`/api/notifications` e pelo polling do cabeçalho da aplicação web.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, Sequence[str], None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # O enum pode ter sido criado por uma instalação legada que não tinha a
    # tabela correspondente. Crie-o apenas se necessário e desabilite a
    # segunda tentativa automática durante `create_table`.
    notification_type = postgresql.ENUM(
        "LEAD_RESPONDED",
        "LEAD_ASSIGNED",
        "SLA_ALERT",
        "CADENCE_DUE",
        name="notification_type",
    )
    notification_type.create(op.get_bind(), checkfirst=True)
    notification_type_for_column = postgresql.ENUM(
        "LEAD_RESPONDED",
        "LEAD_ASSIGNED",
        "SLA_ALERT",
        "CADENCE_DUE",
        name="notification_type",
        create_type=False,
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("notification_type", notification_type_for_column, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("lead_id", sa.UUID(), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_user_id_read",
        "notifications",
        ["user_id", "is_read"],
    )
    op.create_index(
        "ix_notifications_created_at",
        "notifications",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_user_id_read", table_name="notifications")
    op.drop_table("notifications")
    postgresql.ENUM(name="notification_type").drop(op.get_bind(), checkfirst=True)