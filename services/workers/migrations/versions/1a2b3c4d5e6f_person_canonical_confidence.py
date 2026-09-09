"""Revision ID: 1a2b3c4d5e6f
Revises: ff8a9b0c1d2e

Onda 1 PR04: Person canônica carrega identidade/contato/verificação e
acionabilidade (mesmos campos já existentes em Contact).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, Sequence[str], None] = "ff8a9b0c1d2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("persons")}
    if "identity_confidence" not in existing:
        op.add_column("persons", sa.Column("identity_confidence", sa.Integer(), nullable=False, server_default="0"))
    if "contact_confidence" not in existing:
        op.add_column("persons", sa.Column("contact_confidence", sa.Integer(), nullable=False, server_default="0"))
    if "source_reliability" not in existing:
        op.add_column("persons", sa.Column("source_reliability", sa.Float(), nullable=False, server_default="0"))
    if "verification_status" not in existing:
        op.add_column("persons", sa.Column("verification_status", sa.String(length=40), nullable=False, server_default="needs_review"))
    if "last_verified_at" not in existing:
        op.add_column("persons", sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True))
    if "routability_type" not in existing:
        op.add_column("persons", sa.Column("routability_type", sa.String(length=24), nullable=False, server_default="UNKNOWN"))
    if "routable" not in existing:
        op.add_column("persons", sa.Column("routable", sa.Boolean(), nullable=False, server_default="false"))
    if "routability_reason" not in existing:
        op.add_column("persons", sa.Column("routability_reason", sa.String(length=80), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("persons")}
    for column in (
        "routability_reason",
        "routable",
        "routability_type",
        "last_verified_at",
        "verification_status",
        "source_reliability",
        "contact_confidence",
        "identity_confidence",
    ):
        if column in existing:
            op.drop_column("persons", column)
