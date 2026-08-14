"""add sales_role to organization_members

Revision ID: b2c3d4e5f6a7b
Revises: 8a1b2c3d4e5f6
Create Date: 2026-08-01

Papéis de venda:
- `organization_members.sales_role` (enum CONSULTOR/ANALYST/MANAGER,
  default CONSULTOR) — papel de venda POR organização: o que o membro
  enxerga/faz (próprio funil vs BI/leitura total).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

sales_role_enum = ENUM(
    'CONSULTOR', 'ANALYST', 'MANAGER',
    name='sales_role', create_type=False,
)

revision: str = 'b2c3d4e5f6a7b'
down_revision: Union[str, Sequence[str], None] = '8a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    sales_role_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'organization_members',
        sa.Column('sales_role', sales_role_enum, nullable=False,
                  server_default='CONSULTOR'),
    )


def downgrade() -> None:
    op.drop_column('organization_members', 'sales_role')
    sales_role_enum.drop(op.get_bind(), checkfirst=True)
