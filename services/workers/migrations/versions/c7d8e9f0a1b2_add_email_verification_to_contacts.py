"""add email verification fields to contacts

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-08-04

Verificação de e-mail (entregabilidade):
- `contacts.email_verified` (Boolean, default false) — entregabilidade passiva
  confirmada (MX presente + não-descartável). Gate do envio automático.
- `contacts.email_verified_at` (DateTime, nullable) — quando a verificação
  rodou pela última vez (para re-verificação periódica).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'b6c7d8e9f0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'contacts',
        sa.Column('email_verified', sa.Boolean(), nullable=False,
                  server_default='false'),
    )
    op.add_column(
        'contacts',
        sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('contacts', 'email_verified_at')
    op.drop_column('contacts', 'email_verified')
