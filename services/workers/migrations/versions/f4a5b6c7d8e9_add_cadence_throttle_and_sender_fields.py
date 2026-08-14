"""add cadence throttle and sender fields

Revision ID: f4a5b6c7d8e9
Revises: e2f3a4b5c6d7
Create Date: 2026-08-06

Warmup/throttling e remetente dedicado:
- `organizations.daily_email_limit` (int, default 40) — teto diário de envios
  automáticos da org (o scheduler `run_due` nunca ultrapassa no dia).
- `organizations.send_window_start` / `send_window_end` (HH:MM, default
  09:00–17:00) — janela de espalhamento horário dos envios automáticos.
- `organization_members.email_from` (string, nullable) — remetente dedicado
  por consultor, para preservar a reputação individual no envio automático.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, Sequence[str], None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'organizations',
        sa.Column('daily_email_limit', sa.Integer(), nullable=False,
                  server_default='40'),
    )
    op.add_column(
        'organizations',
        sa.Column('send_window_start', sa.String(length=5), nullable=False,
                  server_default='09:00'),
    )
    op.add_column(
        'organizations',
        sa.Column('send_window_end', sa.String(length=5), nullable=False,
                  server_default='17:00'),
    )
    op.add_column(
        'organization_members',
        sa.Column('email_from', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('organization_members', 'email_from')
    op.drop_column('organizations', 'send_window_end')
    op.drop_column('organizations', 'send_window_start')
    op.drop_column('organizations', 'daily_email_limit')
