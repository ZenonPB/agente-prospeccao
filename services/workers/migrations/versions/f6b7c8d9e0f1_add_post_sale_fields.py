"""add post-sale fields and FollowUpStep.POST_SALE

Revision ID: f6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-08-06

Roadmap-leads C.3 — pós-venda (largar a planilha):
- `leads.post_sale_contacted_at` (DateTime) — DATA CONTATO PÓS-VENDA;
- `leads.post_sale_channel` (enum `post_sale_channel`: WHATSAPP/EMAIL) — canal;
- `follow_up_step` ganha o valor `POST_SALE` para o acompanhamento pós-cliente
  usar o mesmo motor da cadência (scheduler `run_due` + `send_step`).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

post_sale_channel_enum = postgresql.ENUM(
    'WHATSAPP', 'EMAIL',
    name='post_sale_channel', create_type=False,
)

revision: str = 'f6b7c8d9e0f1'
down_revision: Union[str, Sequence[str], None] = 'f5a6b7c8d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    post_sale_channel_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('leads', sa.Column('post_sale_contacted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('leads', sa.Column('post_sale_channel', post_sale_channel_enum, nullable=True))
    op.execute("ALTER TYPE follow_up_step ADD VALUE IF NOT EXISTS 'POST_SALE'")


def downgrade() -> None:
    op.drop_column('leads', 'post_sale_channel')
    op.drop_column('leads', 'post_sale_contacted_at')
    post_sale_channel_enum.drop(op.get_bind(), checkfirst=True)
    # O enum `follow_up_step` não é revertido (PG não remove valores de enum).