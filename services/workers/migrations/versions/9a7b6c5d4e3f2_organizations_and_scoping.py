"""add organizations, memberships and scope campaigns/leads/jobs to org

Revision ID: 9a7b6c5d4e3f2
Revises: 8e3c88135f1b
Create Date: 2026-08-01

Multi-tenant — isolamento por organização:
- Nova tabela `organizations` (workspace que agrupa usuários e isola dados).
- Nova tabela `organization_members` (vínculo user<->org com papel).
- Nova tabela `invites` (convite por e-mail para ingressar na org).
- `campaigns.organization_id` (FK, not null após backfill).
- `leads.organization_id` (FK, not null após backfill).
- `jobs.organization_id` (FK, nullable — jobs legados sem campanha).
- Substitui a UNIQUE global de `leads.place_id` pela composta
  `uq_leads_org_place_id (organization_id, place_id)` — dois usuários podem
  prospectar o mesmo lugar, desde que em orgs diferentes.

Backfill (uma vez, para dados existentes):
- Para cada `users` sem org: cria `organizations` pessoal "{name}'s workspace"
  (slug gerado de email), membership owner, e propaga `organization_id` para
  campanhas/leads/jobs do usuário.
"""
from typing import Sequence, Union
import re
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM


revision: str = '9a7b6c5d4e3f2'
down_revision: Union[str, Sequence[str], None] = '8e3c88135f1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _slugify(name: str, email: str, suffix: str = "") -> str:
    """Gera um slug único aproximado a partir de nome/email."""
    base = re.sub(r'[^a-z0-9]+', '-', (name or email).lower()).strip('-')
    if not base:
        base = "workspace"
    return f"{base}{suffix}"[:120]


def _make_slug(conn, base_slug: str) -> str:
    """Garante unicidade do slug consultando a tabela na conexão."""
    slug = base_slug
    i = 2
    while True:
        exists = conn.execute(
            sa.text("SELECT 1 FROM organizations WHERE slug = :slug"),
            {"slug": slug},
        ).fetchone()
        if not exists:
            return slug
        slug = f"{base_slug}-{i}"
        i += 1


def upgrade() -> None:
    conn = op.get_bind()

    # --- Enum de papel de organização ---
    org_role = ENUM('owner', 'admin', 'member', name='organization_role')
    org_role.create(conn, checkfirst=True)
    # Colunas que usam o enum SEM disparar CREATE TYPE novamente (create_type=False).
    org_role_col = ENUM('owner', 'admin', 'member', name='organization_role', create_type=False)

    # --- Tabelas novas ---
    op.create_table(
        'organizations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
    )
    op.create_unique_constraint('uq_organizations_slug', 'organizations', ['slug'])

    op.create_table(
        'organization_members',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', org_role_col, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_unique_constraint('uq_organization_members_org_user',
                                'organization_members', ['organization_id', 'user_id'])
    op.create_index('ix_organization_members_user_id', 'organization_members', ['user_id'])

    op.create_table(
        'invites',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('organization_id', UUID(as_uuid=True),
                  sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', org_role_col, nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_unique_constraint('uq_invites_token', 'invites', ['token'])
    op.create_index('ix_invites_organization_id', 'invites', ['organization_id'])
    op.create_index('ix_invites_email', 'invites', ['email'])

    # --- organization_id nas tabelas existentes (nullable para backfill) ---
    op.add_column('campaigns', sa.Column('organization_id', UUID(as_uuid=True),
                                         sa.ForeignKey('organizations.id'), nullable=True))
    op.add_column('leads', sa.Column('organization_id', UUID(as_uuid=True),
                                     sa.ForeignKey('organizations.id'), nullable=True))
    op.add_column('jobs', sa.Column('organization_id', UUID(as_uuid=True),
                                    sa.ForeignKey('organizations.id'), nullable=True))

    # --- Backfill: uma org pessoal por usuário, com membros e propagação ---
    users = conn.execute(sa.text(
        "SELECT id, email, name FROM users ORDER BY created_at"
    )).fetchall()

    for user in users:
        user_id = str(user[0])
        email = user[1] or ""
        name = user[2] or email.split("@")[0]

        org_id = str(uuid.uuid4())
        slug = _make_slug(conn, _slugify(name, email))

        conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"
            ),
            {"id": org_id, "name": f"{name}'s workspace", "slug": slug},
        )
        conn.execute(
            sa.text(
                "INSERT INTO organization_members (id, organization_id, user_id, role) "
                "VALUES (:id, :org_id, :user_id, 'owner')"
            ),
            {"id": str(uuid.uuid4()), "org_id": org_id, "user_id": user_id},
        )
        conn.execute(
            sa.text("UPDATE campaigns SET organization_id = :org_id WHERE user_id = :user_id"),
            {"org_id": org_id, "user_id": user_id},
        )
        conn.execute(
            sa.text(
                "UPDATE leads SET organization_id = :org_id "
                "WHERE campaign_id IN (SELECT id FROM campaigns WHERE user_id = :user_id)"
            ),
            {"org_id": org_id, "user_id": user_id},
        )
        conn.execute(
            sa.text(
                "UPDATE jobs SET organization_id = :org_id "
                "WHERE campaign_id IN (SELECT id FROM campaigns WHERE user_id = :user_id)"
            ),
            {"org_id": org_id, "user_id": user_id},
        )

    # Leads/jobs sem campanha (legados coletados via `python -m src.main`) pertencem
    # a nenhuma org ainda — deixa-os sem organization_id (jobs) e marca leads
    # órfãos com a org do primeiro usuário para não quebrar a NOT NULL.
    # Leads órfãos (sem campaign) — se existir ao menos um usuário, atribui a ele.
    first_org = conn.execute(sa.text(
        "SELECT organization_id FROM organization_members ORDER BY created_at LIMIT 1"
    )).fetchone()
    if first_org:
        conn.execute(
            sa.text(
                "UPDATE leads SET organization_id = :org_id "
                "WHERE organization_id IS NULL"
            ),
            {"org_id": str(first_org[0])},
        )

    # --- Tornar NOT NULL onde obrigatório ---
    op.alter_column('campaigns', 'organization_id',
                    existing_type=UUID(as_uuid=True), nullable=False)
    op.alter_column('leads', 'organization_id',
                    existing_type=UUID(as_uuid=True), nullable=False)

    # --- UNIQUE global de place_id -> composta por org ---
    # PG nomeia a UNIQUE de coluna como '<tabela>_<coluna>_key'.
    op.drop_constraint('leads_place_id_key', 'leads', type_='unique')
    op.create_unique_constraint('uq_leads_org_place_id', 'leads',
                                ['organization_id', 'place_id'])
    op.create_index('ix_campaigns_organization_id', 'campaigns', ['organization_id'])
    op.create_index('ix_leads_organization_id', 'leads', ['organization_id'])


def downgrade() -> None:
    conn = op.get_bind()

    op.drop_index('ix_leads_organization_id', table_name='leads')
    op.drop_index('ix_campaigns_organization_id', table_name='campaigns')
    op.drop_constraint('uq_leads_org_place_id', 'leads', type_='unique')
    op.create_unique_constraint('leads_place_id_key', 'leads', ['place_id'])

    op.drop_column('leads', 'organization_id')
    op.drop_column('campaigns', 'organization_id')
    op.drop_column('jobs', 'organization_id')

    op.drop_index('ix_invites_email', table_name='invites')
    op.drop_index('ix_invites_organization_id', table_name='invites')
    op.drop_table('invites')
    op.drop_index('ix_organization_members_user_id', table_name='organization_members')
    op.drop_table('organization_members')
    op.drop_table('organizations')
    ENUM(name='organization_role').drop(conn, checkfirst=True)
