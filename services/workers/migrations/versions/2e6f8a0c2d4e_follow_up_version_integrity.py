"""Revision ID: 2e6f8a0c2d4e
Revises: 2d5e7f9b1c3f

Garante que uma etapa da cadência não possua duas versões com o mesmo número.
O cálculo do próximo número ocorre na aplicação; a constraint evita colisão
em edições concorrentes e mantém o histórico íntegro.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2e6f8a0c2d4e"
down_revision: Union[str, Sequence[str], None] = "2d5e7f9b1c3f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CONSTRAINT_NAME = "uq_follow_up_versions_follow_up_version"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "follow_up_versions" not in inspector.get_table_names():
        return
    existing = {
        item["name"]
        for item in inspector.get_unique_constraints("follow_up_versions")
        if item.get("name")
    }
    if CONSTRAINT_NAME not in existing:
        op.create_unique_constraint(
            CONSTRAINT_NAME,
            "follow_up_versions",
            ["follow_up_id", "version_number"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "follow_up_versions" not in inspector.get_table_names():
        return
    existing = {
        item["name"]
        for item in inspector.get_unique_constraints("follow_up_versions")
        if item.get("name")
    }
    if CONSTRAINT_NAME in existing:
        op.drop_constraint(CONSTRAINT_NAME, "follow_up_versions", type_="unique")