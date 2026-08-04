"""fix go-live 2.1/4.3/4.4: leads.name/cnpj/address + normalized_domain + campos de vendas

Revision ID: a5b6c7d8e9f0
Revises: 72ce8b2f4cf3
Create Date: 2026-08-04

Bloqueador 2.1 (auditoria): CSV e CNAE quebravam porque `leads` não tinha
`name`, `cnpj` nem `address` (o código já os usava).

4.3: `normalized_domain` — domínio canônico (sem scheme/www, lowercase) para
dedupe único entre Places/CSV/CNAE.

4.4: campos de trabalho do consultor — `whatsapp`, `notes`, `next_action_at`,
`last_contacted_at`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a5b6c7d8e9f0'
down_revision: Union[str, Sequence[str], None] = '72ce8b2f4cf3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('name', sa.String(length=255), nullable=True))
    op.add_column('leads', sa.Column('cnpj', sa.String(length=14), nullable=True))
    op.add_column('leads', sa.Column('address', sa.String(length=500), nullable=True))
    op.add_column('leads', sa.Column('normalized_domain', sa.String(length=255), nullable=True))
    op.add_column('leads', sa.Column('whatsapp', sa.String(length=50), nullable=True))
    op.add_column('leads', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('leads', sa.Column('next_action_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('leads', sa.Column('last_contacted_at', sa.DateTime(timezone=True), nullable=True))

    # Backfill: `name` herda `company_name` (leads existentes de Places).
    op.execute("UPDATE leads SET name = company_name WHERE name IS NULL")

    # Backfill: `cnpj` a partir de `company_records` (sem conflito na org).
    op.execute(
        """
        UPDATE leads l SET cnpj = cr.cnpj
        FROM company_records cr
        WHERE cr.lead_id = l.id AND cr.cnpj IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM leads l2
            JOIN company_records cr2 ON cr2.lead_id = l2.id
            WHERE l2.organization_id = l.organization_id AND cr2.cnpj = cr.cnpj AND l2.id <> l.id
          )
        """
    )

    # Backfill: `normalized_domain` canônico a partir do website, mantendo só a
    # primeira ocorrência por (org, domínio) para o unique não estourar.
    op.execute(
        """
        UPDATE leads l SET normalized_domain = d.domain
        FROM (
            SELECT DISTINCT ON (organization_id, domain) id, organization_id, domain
            FROM (
                SELECT id, organization_id,
                       lower(
                           regexp_replace(
                               regexp_replace(
                                   regexp_replace(website, '^https?://', ''),
                                   '^www\\.', ''),
                               '/.*$', ''))
                       AS domain
                FROM leads
                WHERE website IS NOT NULL AND website <> ''
            ) s
            ORDER BY organization_id, domain, created_at
        ) d
        WHERE l.id = d.id
        """
    )

    op.create_unique_constraint('uq_leads_org_cnpj', 'leads', ['organization_id', 'cnpj'])
    op.create_unique_constraint('uq_leads_org_normalized_domain', 'leads', ['organization_id', 'normalized_domain'])
    op.create_index('ix_leads_normalized_domain', 'leads', ['normalized_domain'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_leads_normalized_domain', table_name='leads')
    op.drop_constraint('uq_leads_org_normalized_domain', 'leads', type_='unique')
    op.drop_constraint('uq_leads_org_cnpj', 'leads', type_='unique')
    op.drop_column('leads', 'last_contacted_at')
    op.drop_column('leads', 'next_action_at')
    op.drop_column('leads', 'notes')
    op.drop_column('leads', 'whatsapp')
    op.drop_column('leads', 'normalized_domain')
    op.drop_column('leads', 'address')
    op.drop_column('leads', 'cnpj')
    op.drop_column('leads', 'name')
