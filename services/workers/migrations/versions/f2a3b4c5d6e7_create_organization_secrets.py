"""create organization_secrets table for BYOK

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-05

BYOK (bring your own key):
- `organization_secrets` — chaves de API próprias por organização
  (`GOOGLE_API_KEY` / `GROQ_API_KEY`), criptografadas em repouso.
- Unique em (organization_id, key_name).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'organization_secrets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('key_name', sa.String(length=60), nullable=False),
        sa.Column('encrypted_value', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  onupdate=sa.func.now()),
        sa.UniqueConstraint('organization_id', 'key_name',
                            name='uq_org_secrets_org_key'),
    )


def downgrade() -> None:
    op.drop_table('organization_secrets')
