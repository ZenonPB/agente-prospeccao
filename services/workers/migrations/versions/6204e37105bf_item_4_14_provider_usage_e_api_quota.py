"""provider_usage e api_quota

Revision ID: 6204e37105bf
Revises: c183a77bc662
Create Date: 2026-08-11 14:48:19.732998

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6204e37105bf'
down_revision: Union[str, Sequence[str], None] = 'c183a77bc662'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Medidor diário de uso de provedores por org/key.
    op.create_table(
        'provider_usage',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('key_name', sa.String(length=60), nullable=False),
        sa.Column('usage_date', sa.Date(), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'organization_id', 'key_name', 'usage_date',
            name='uq_provider_usage_org_key_date',
        ),
    )
    # Sobrescrita opcional do teto diário por provedor (BYOK vs pool).
    op.add_column(
        'organizations',
        sa.Column('api_quota', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('organizations', 'api_quota')
    op.drop_table('provider_usage')
