"""add_lead_value_expected_close_and_lost_reason

Revision ID: 69f0f84a9739
Revises: 02a4353c47a7
Create Date: 2026-08-10 21:07:30.077162

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '69f0f84a9739'
down_revision: Union[str, Sequence[str], None] = '02a4353c47a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('value', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('leads', sa.Column('expected_close_date', sa.DateTime(timezone=True), nullable=True))
    lost_reason_enum = sa.Enum('PRECO', 'PRAZO', 'NAO_RESPONDEU', 'CONCORRENTE', 'OUTRO', name='lost_reason')
    lost_reason_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('leads', sa.Column('lost_reason', lost_reason_enum, nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'lost_reason')
    op.drop_column('leads', 'expected_close_date')
    op.drop_column('leads', 'value')
