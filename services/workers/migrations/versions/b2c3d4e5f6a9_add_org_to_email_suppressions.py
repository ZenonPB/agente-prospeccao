"""add organization_id to email_suppressions

Revision ID: b2c3d4e5f6a9
Revises: a1b2c3d4e5f7
Create Date: 2026-08-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b2c3d4e5f6a9'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('email_suppressions', sa.Column('organization_id', sa.UUID(), nullable=True))
    op.create_index('ix_email_suppressions_org_created', 'email_suppressions', ['organization_id', 'created_at'], unique=False)
    op.create_foreign_key('fk_email_suppressions_organization', 'email_suppressions', 'organizations', ['organization_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_email_suppressions_organization', 'email_suppressions', type_='foreignkey')
    op.drop_index('ix_email_suppressions_org_created', table_name='email_suppressions')
    op.drop_column('email_suppressions', 'organization_id')