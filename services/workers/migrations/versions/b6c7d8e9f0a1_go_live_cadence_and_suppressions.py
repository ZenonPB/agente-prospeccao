"""go-live 2.3/3.2/4.1: attempts+message_id em follow_ups, org.email_from, email_suppressions

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-08-04

2.3: `send_step` passa a respeitar `scheduled_at` (nenhuma rajada no
auto_send) — não exige coluna, mas o controle de tentativas abaixo o suporta.

3.2: `follow_ups.attempts` (retry de falhas transitórias com teto) +
`follow_ups.message_id` (threading) + tabela `email_suppressions` (bounce
permanente 5xx suprime re-envios em qualquer cadência).

4.1: `organizations.email_from` — remetente próprio por org.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b6c7d8e9f0a1'
down_revision: Union[str, Sequence[str], None] = 'a5b6c7d8e9f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('follow_ups', sa.Column('attempts', sa.Integer(), server_default='0', nullable=False))
    op.add_column('follow_ups', sa.Column('message_id', sa.String(length=255), nullable=True))
    op.add_column('organizations', sa.Column('email_from', sa.String(length=255), nullable=True))

    op.create_table(
        'email_suppressions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_email_suppressions_email', 'email_suppressions', ['email'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_email_suppressions_email', table_name='email_suppressions')
    op.drop_table('email_suppressions')
    op.drop_column('organizations', 'email_from')
    op.drop_column('follow_ups', 'message_id')
    op.drop_column('follow_ups', 'attempts')
