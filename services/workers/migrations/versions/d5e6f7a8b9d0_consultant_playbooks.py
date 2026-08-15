"""playbooks por consultor

Revision ID: d5e6f7a8b9d0
Revises: c4d5e6f7a8b9
Create Date: 2026-08-14

Repositório de mensagens que funcionaram, anotadas pelo próprio time.
Cada consultor (autor) salva subject + body + vertical/segmento no seu
playbook; outros membros da org podem ler para se inspirar, mas só o
autor ou admin pode editar/remover.

Tabela:
- consultant_playbooks (id, org, author, vertical, subject, body, tags, timestamps)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = 'd5e6f7a8b9d0'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'consultant_playbooks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('author_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('vertical', sa.String(length=120), nullable=True),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('tags', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  onupdate=sa.func.now()),
    )
    op.create_index(
        'ix_consultant_playbooks_org', 'consultant_playbooks',
        ['organization_id'], unique=False,
    )
    op.create_index(
        'ix_consultant_playbooks_author', 'consultant_playbooks',
        ['author_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_consultant_playbooks_author', table_name='consultant_playbooks')
    op.drop_index('ix_consultant_playbooks_org', table_name='consultant_playbooks')
    op.drop_table('consultant_playbooks')
