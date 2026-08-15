"""webhook genérico + link de agendamento por organização

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-08-14

Cada organização pode configurar:
- `webhook_url` — URL pública que recebe eventos de lead (criado/status/
  conversão) em POST JSON;
- `webhook_secret` — segredo compartilhado enviado em `X-Webhook-Secret`
  para o consumidor validar a origem;
- `scheduling_url` — link de agendamento (Cal.com/Calendly) injetado no
  outreach como CTA opcional quando preenchido.

Apenas owner/admin configuram via `PATCH /api/orgs/{id}`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'organizations',
        sa.Column('webhook_url', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'organizations',
        sa.Column('webhook_secret', sa.String(length=64), nullable=True),
    )
    op.add_column(
        'organizations',
        sa.Column('scheduling_url', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('organizations', 'scheduling_url')
    op.drop_column('organizations', 'webhook_secret')
    op.drop_column('organizations', 'webhook_url')
