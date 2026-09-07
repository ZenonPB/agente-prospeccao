"""persist event decision maker and human action recommendation

Revision ID: aa6b7c8d9e0f
Revises: ff5a6b7c8d9e
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "aa6b7c8d9e0f"
down_revision: Union[str, Sequence[str], None] = "ff5a6b7c8d9e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("event_opportunities")}
    definitions = (
        sa.Column("decision_maker_id", sa.UUID(), nullable=True),
        sa.Column("decision_maker_status", sa.String(length=24), server_default="not_found", nullable=False),
        sa.Column("recommended_channel", sa.String(length=32), nullable=True),
        sa.Column("action_status", sa.String(length=24), server_default="needs_review", nullable=False),
        sa.Column("next_action", sa.Text(), nullable=True),
    )
    for column in definitions:
        if column.name not in columns:
            op.add_column("event_opportunities", column)
    foreign_keys = {
        fk["name"] for fk in inspector.get_foreign_keys("event_opportunities") if fk.get("name")
    }
    if "fk_event_opportunities_decision_maker" not in foreign_keys:
        op.create_foreign_key(
            "fk_event_opportunities_decision_maker",
            "event_opportunities",
            "contacts",
            ["decision_maker_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    op.drop_constraint("fk_event_opportunities_decision_maker", "event_opportunities", type_="foreignkey")
    op.drop_column("event_opportunities", "next_action")
    op.drop_column("event_opportunities", "action_status")
    op.drop_column("event_opportunities", "recommended_channel")
    op.drop_column("event_opportunities", "decision_maker_status")
    op.drop_column("event_opportunities", "decision_maker_id")