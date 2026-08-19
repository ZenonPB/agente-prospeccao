"""add_companies_persons_webhook_logs

Revision ID: 2b137f2dc6f5
Revises: f7a8b9c0d1e2
Create Date: 2026-08-18 22:05:57.088843

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2b137f2dc6f5'
down_revision: Union[str, Sequence[str], None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('companies',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('cnpj', sa.String(length=20), nullable=True),
    sa.Column('website', sa.String(length=255), nullable=True),
    sa.Column('normalized_domain', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('address', sa.String(length=500), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('state', sa.String(length=100), nullable=True),
    sa.Column('country', sa.String(length=100), nullable=True),
    sa.Column('category', sa.String(length=100), nullable=True),
    sa.Column('google_rating', sa.Float(), nullable=True),
    sa.Column('google_rating_count', sa.Integer(), nullable=True),
    sa.Column('google_maps_uri', sa.String(length=255), nullable=True),
    sa.Column('company_linkedin_url', sa.String(length=255), nullable=True),
    sa.Column('instagram_url', sa.String(length=255), nullable=True),
    sa.Column('raw_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'cnpj', name='uq_companies_org_cnpj'),
    sa.UniqueConstraint('organization_id', 'normalized_domain', name='uq_companies_org_domain')
    )
    op.create_table('webhook_logs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('event_type', sa.String(length=100), nullable=False),
    sa.Column('target_url', sa.String(length=500), nullable=False),
    sa.Column('status_code', sa.Integer(), nullable=True),
    sa.Column('success', sa.Boolean(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('response_body', sa.Text(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_webhook_logs_org_created', 'webhook_logs', ['organization_id', 'created_at'], unique=False)
    op.create_table('persons',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('role', postgresql.ENUM('SOCIO', 'ADMINISTRADOR', 'CEO', 'DIRETOR', 'OUTRO', name='contact_role', create_type=False), nullable=True),
    sa.Column('role_label', sa.String(length=100), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('document_cpf', sa.String(length=20), nullable=True),
    sa.Column('confidence', sa.Integer(), nullable=True),
    sa.Column('email_verified', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('linkedin_url', sa.String(length=255), nullable=True),
    sa.Column('linkedin_confidence', sa.Integer(), nullable=True),
    sa.Column('source', sa.String(length=60), nullable=True),
    sa.Column('raw_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('leads', sa.Column('company_id', sa.UUID(), nullable=True))
    op.add_column('leads', sa.Column('primary_person_id', sa.UUID(), nullable=True))
    op.create_foreign_key(None, 'leads', 'persons', ['primary_person_id'], ['id'])
    op.create_foreign_key(None, 'leads', 'companies', ['company_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, 'leads', type_='foreignkey')
    op.drop_constraint(None, 'leads', type_='foreignkey')
    op.drop_column('leads', 'primary_person_id')
    op.drop_column('leads', 'company_id')
    op.drop_table('persons')
    op.drop_index('ix_webhook_logs_org_created', table_name='webhook_logs')
    op.drop_table('webhook_logs')
    op.drop_table('companies')
