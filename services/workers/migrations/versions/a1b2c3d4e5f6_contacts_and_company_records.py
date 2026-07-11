"""add contacts and company_records tables (sprint 1: decisor + CNPJ)

Revision ID: a1b2c3d4e5f6
Revises: c4a1f2e8b9d0
Create Date: 2026-07-09 20:00:00.000000

Sprint 1 — Decisor e CNPJ:
- Tabela `contacts` com decisor(s) do lead (sócio/administrador via Receita).
  Lead puede ter múltiplos; um está marcado is_primary=True.
- Tabela `company_records` (1:1 com lead) — snapshot cadastral da Receita:
  razão social, porte, CNAE, capital_social, situação, idade, sócios expostos
  em raw_data.
- Enum `contact_role` (SOCIO, ADMINISTRADOR, CEO, DIRETOR, OUTRO).

Não altera `leads` — o decisor vive em `contacts` (relação 1:N) e os dados
cadastrais em `company_records` (relação 1:0..1), separados para permitir
re-análise sem re-bater a API e para que múltiplos decisores possam coexistir.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'c4a1f2e8b9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enum contact_role — criado fora da coluna para downgrade limpo.
    # `create_type=True` default; SQLAlchemy cuidará de criar e não duplicar.
    contact_role = sa.Enum(
        'SOCIO', 'ADMINISTRADOR', 'CEO', 'DIRETOR', 'OUTRO',
        name='contact_role',
    )

    op.create_table(
        'contacts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('lead_id', UUID(as_uuid=True),
                   sa.ForeignKey('leads.id'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', contact_role, nullable=True),
        sa.Column('role_label', sa.String(length=100)),
        sa.Column('email', sa.String(length=255)),
        sa.Column('phone', sa.String(length=50)),
        sa.Column('document_cpf', sa.String(length=20)),
        sa.Column('confidence', sa.Integer(), server_default='0'),
        sa.Column('is_primary', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('source', sa.String(length=60), server_default="'cnpj_receita'"),
        sa.Column('raw_data', JSONB),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_contacts_lead_id', 'contacts', ['lead_id'])

    op.create_table(
        'company_records',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('lead_id', UUID(as_uuid=True),
                   sa.ForeignKey('leads.id'), nullable=False, unique=True),
        sa.Column('cnpj', sa.String(length=20)),
        sa.Column('razao_social', sa.String(length=255)),
        sa.Column('nome_fantasia', sa.String(length=255)),
        sa.Column('porte', sa.String(length=50)),
        sa.Column('porte_label', sa.String(length=100)),
        sa.Column('natureza_juridica', sa.String(length=255)),
        sa.Column('capital_social', sa.Numeric(14, 2)),
        sa.Column('situacao_cadastral', sa.String(length=50)),
        sa.Column('data_abertura', sa.String(length=20)),
        sa.Column('idade_anos', sa.Integer()),
        sa.Column('cnae_principal', sa.String(length=20)),
        sa.Column('cnae_principal_label', sa.String(length=255)),
        sa.Column('cnae_secundarios', JSONB),
        sa.Column('endereco', JSONB),
        sa.Column('municipios_ativos', JSONB),
        sa.Column('raw_data', JSONB),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table('company_records')
    op.drop_index('ix_contacts_lead_id', table_name='contacts')
    op.drop_table('contacts')
    sa.Enum(name='contact_role').drop(op.get_bind(), checkfirst=True)
