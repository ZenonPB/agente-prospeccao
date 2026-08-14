"""org_audit_log — trilha de eventos administrativos da organização

Revision ID: bff05fb7eb01
Revises: ef4d92ca2c1a
Create Date: 2026-08-14 15:50:06.048708

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'bff05fb7eb01'
down_revision: Union[str, Sequence[str], None] = 'ef4d92ca2c1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'org_audit_log',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('actor_id', sa.UUID(), nullable=True),
        sa.Column('actor_name', sa.String(length=255), nullable=True),
        sa.Column('actor_email', sa.String(length=255), nullable=True),
        sa.Column(
            'event',
            sa.Enum(
                'ORG_CREATED', 'ORG_RENAMED', 'ORG_SETTINGS_UPDATED',
                'MEMBER_ROLE_CHANGED', 'MEMBER_REMOVED', 'MEMBER_LEFT',
                'OWNER_TRANSFERRED', 'INVITE_CREATED', 'INVITE_ACCEPTED',
                'INVITE_REVOKED', 'SECRET_SET', 'SECRET_DELETED',
                'SALES_TARGET_UPSERTED', 'SALES_TARGET_DELETED',
                name='org_audit_event',
            ),
            nullable=False,
        ),
        sa.Column('target_type', sa.String(length=60), nullable=True),
        sa.Column('target_id', sa.String(length=60), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_org_audit_log_org_created', 'org_audit_log',
        ['organization_id', 'created_at'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_org_audit_log_org_created', table_name='org_audit_log')
    op.drop_table('org_audit_log')
