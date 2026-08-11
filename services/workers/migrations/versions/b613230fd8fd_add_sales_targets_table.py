"""add_sales_targets_table

Revision ID: b613230fd8fd
Revises: 69f0f84a9739
Create Date: 2026-08-10 21:39:01.189952

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b613230fd8fd'
down_revision: Union[str, Sequence[str], None] = '69f0f84a9739'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sales_targets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('month', sa.String(length=7), nullable=False),
        sa.Column('meetings_target', sa.Integer(), nullable=False),
        sa.Column('revenue_target', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'user_id', 'month', name='uq_sales_targets_org_user_month'),
    )
    op.create_index(op.f('ix_sales_targets_month'), 'sales_targets', ['month'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sales_targets_month'), table_name='sales_targets')
    op.drop_table('sales_targets')