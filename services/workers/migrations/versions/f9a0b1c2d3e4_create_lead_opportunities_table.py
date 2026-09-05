"""create lead_opportunities table

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3

Adiciona a tabela `lead_opportunities` para persistir o resultado do
OfferMatcher (1 lead -> N oportunidades simultaneas), com upsert idempotente
por (lead_id, offer_key).

Campos:
- id (PK), lead_id (FK -> leads.id), organization_id (FK -> organizations.id)
- offer_key, profile_key (denormalizados para consulta rapida)
- score INT, resolved_from TEXT
- evidence JSONB (lista de strings), signals_matched JSONB, signals_missing JSONB
- created_at, updated_at

Indice composto (lead_id, offer_key) UNIQUE -> ON CONFLICT DO UPDATE no servico.
Indice em (organization_id) para queries multi-tenant.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_opportunities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("offer_key", sa.String(length=64), nullable=False),
        sa.Column("profile_key", sa.String(length=64), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved_from", sa.String(length=16), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("signals_matched", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("signals_missing", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lead_id", "offer_key", name="uq_lead_opportunities_lead_offer"),
    )
    op.create_index(
        "ix_lead_opportunities_organization_id",
        "lead_opportunities",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_lead_opportunities_organization_id", table_name="lead_opportunities")
    op.drop_table("lead_opportunities")