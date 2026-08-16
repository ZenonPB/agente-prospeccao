"""add variant column to messages for per-message A/B tracking

Revision ID: f7a8b9c0d1e2
Revises: f6b7c8d9e0f1
Create Date: 2026-08-15

Tracking individual por variante (A/B) — sem o proxy por `FollowUp.variant`
que misturava aberturas de etapas distintas quando o mesmo `tracking_token`
era reutilizado ou compartilhado entre variantes.

- `messages.variant` (String 32, nullable) — rótulo da variante A/B efetivamente
  entregue (espelha `follow_ups.variant` no momento do envio).
- Quando uma resposta inbound chega, o serviço cria uma `Message`
  espelho (`is_response=True`) com `variant` derivado da última `Message`
  enviada do lead antes da resposta. Isso permite medir taxa de resposta
  por variante sem dupla-contagem entre etapas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = 'e6f7a8b9c0d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('messages', sa.Column('variant', sa.String(length=32), nullable=True))
    op.create_index(
        'ix_messages_variant',
        'messages',
        ['variant'],
        postgresql_where=sa.text('variant IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_messages_variant', table_name='messages')
    op.drop_column('messages', 'variant')
