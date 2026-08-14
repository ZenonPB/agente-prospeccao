"""add email open/click tracking fields

Revision ID: e2f3a4b5c6d7
Revises: d8e9f0a2b3c4
Create Date: 2026-08-05

Rastreamento de abertura e clique:
- `messages.tracking_token` (unique) — token do pixel/redirect por envio.
- `messages.opened_at` / `messages.clicked_at` — quando abriu/clicou.
- `follow_ups.tracking_token` — liga a etapa da cadência ao `Message`
  correspondente (para o painel expor abertura/clique).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'd8e9f0a2b3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('tracking_token', sa.String(length=64), nullable=True))
    op.add_column('messages', sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('messages', sa.Column('clicked_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint('uq_messages_tracking_token', 'messages', ['tracking_token'])
    op.add_column('follow_ups', sa.Column('tracking_token', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('follow_ups', 'tracking_token')
    op.drop_constraint('uq_messages_tracking_token', 'messages', type_='unique')
    op.drop_column('messages', 'clicked_at')
    op.drop_column('messages', 'opened_at')
    op.drop_column('messages', 'tracking_token')