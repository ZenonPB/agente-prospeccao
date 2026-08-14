"""add invited_by_id and sales_role to invites

Revision ID: c3d4e5f6a7b8c
Revises: b2c3d4e5f6a7b
Create Date: 2026-08-04

Convites + org switcher:
- `invites.invited_by_id` (FK users, nullable) — quem enviou o convite.
- `invites.sales_role` (enum sales_role, default CONSULTOR) — papel de venda
  atribuído ao convidado quando ele aceita.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM

sales_role_enum = ENUM(
    'CONSULTOR', 'ANALYST', 'MANAGER',
    name='sales_role', create_type=False,
)

revision: str = 'c3d4e5f6a7b8c'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'invites',
        sa.Column('invited_by_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id'), nullable=True),
    )
    op.add_column(
        'invites',
        sa.Column('sales_role', sales_role_enum, nullable=False,
                  server_default='CONSULTOR'),
    )


def downgrade() -> None:
    op.drop_column('invites', 'sales_role')
    op.drop_column('invites', 'invited_by_id')
