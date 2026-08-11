"""add_sla_days_to_organizations

Revision ID: c24a13047b0e
Revises: b613230fd8fd
Create Date: 2026-08-10 22:09:36.876261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c24a13047b0e'
down_revision: Union[str, Sequence[str], None] = 'b613230fd8fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('organizations', sa.Column('sla_qualified_no_contact_days', sa.Integer(), server_default='5', nullable=False))
    op.add_column('organizations', sa.Column('sla_responded_no_next_action_days', sa.Integer(), server_default='2', nullable=False))
    op.add_column('organizations', sa.Column('sla_opened_no_response_days', sa.Integer(), server_default='2', nullable=False))


def downgrade() -> None:
    op.drop_column('organizations', 'sla_opened_no_response_days')
    op.drop_column('organizations', 'sla_responded_no_next_action_days')
    op.drop_column('organizations', 'sla_qualified_no_contact_days')
