"""Ativação atômica de snapshot do Registry (membership versionado + ACTIVE).

Revision ID: e5f6a7b8c9d0
Revises: f2b3c4d5e700

Separa provenance de visibilidade: `registry_companies.source_snapshot`
continua registrando a última observação do conteúdo; `is_active` + a tabela
`registry_snapshot_members` decidem o universo que a descoberta enxerga.
O importer escreve em staging (`registry_staging_*`) e a ativação aplica ao
canônico em transação única — import com falha não altera o snapshot ativo.

Backfill honesto: reconstrói membership apenas para o COMPLETED mais recente
de cada source a partir de `source_snapshot`, e o marca ACTIVE. Snapshots
COMPLETED mais antigos não têm membership reconstruível e seguem sem
visibilidade histórica até a próxima importação real.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "f2b3c4d5e700"
branch_labels = None
depends_on = None


def backfill(conn: sa.Connection) -> None:
    """Reconstrói membership + ACTIVE para o COMPLETED mais recente por source.

    Recebe conexão pura para ser reutilizável em teste sobre estado legado.
    Idempotente: `ON CONFLICT DO NOTHING` + `WHERE NOT EXISTS`.
    """
    conn.execute(sa.text("""
        INSERT INTO registry_snapshot_members (snapshot_id, cnpj)
        SELECT latest.id, rc.cnpj
        FROM registry_companies rc
        JOIN LATERAL (
            SELECT s.id
            FROM registry_snapshots s
            WHERE s.source = rc.source
              AND s.status = 'COMPLETED'
            ORDER BY s.snapshot_month DESC
            LIMIT 1
        ) latest ON true
        WHERE rc.source_snapshot = (
            SELECT s2.snapshot_month
            FROM registry_snapshots s2
            WHERE s2.id = latest.id
        )
        ON CONFLICT DO NOTHING
    """))
    conn.execute(sa.text("""
        UPDATE registry_snapshots s
        SET is_active = TRUE
        WHERE s.status = 'COMPLETED'
          AND NOT EXISTS (
            SELECT 1 FROM registry_snapshots other
            WHERE other.source = s.source AND other.is_active
          )
          AND s.snapshot_month = (
            SELECT MAX(s3.snapshot_month)
            FROM registry_snapshots s3
            WHERE s3.source = s.source AND s3.status = 'COMPLETED'
          )
    """))


def upgrade() -> None:
    op.add_column(
        "registry_snapshots",
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
    )
    op.create_index(
        "uq_registry_snapshots_active_per_source",
        "registry_snapshots", ["source"], unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "registry_snapshot_members",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("registry_snapshots.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("cnpj", sa.String(length=14), primary_key=True),
    )
    op.create_index("ix_registry_members_snapshot",
                    "registry_snapshot_members", ["snapshot_id"])
    op.create_index("ix_registry_members_cnpj",
                    "registry_snapshot_members", ["cnpj"])
    op.create_table(
        "registry_staging_companies",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("registry_snapshots.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("cnpj", sa.String(length=14), primary_key=True),
        sa.Column("cnpj_basico", sa.String(length=8), nullable=False),
        sa.Column("razao_social", sa.Text(), nullable=True),
        sa.Column("nome_fantasia", sa.Text(), nullable=True),
        sa.Column("matriz", sa.Boolean(), nullable=True),
        sa.Column("situacao", sa.String(length=2), nullable=True),
        sa.Column("data_situacao", sa.Date(), nullable=True),
        sa.Column("motivo_situacao", sa.String(length=10), nullable=True),
        sa.Column("cidade_exterior", sa.Text(), nullable=True),
        sa.Column("pais_cod", sa.String(length=3), nullable=True),
        sa.Column("data_inicio", sa.Date(), nullable=True),
        sa.Column("cnae_principal", sa.String(length=7), nullable=True),
        sa.Column("natureza_juridica", sa.String(length=4), nullable=True),
        sa.Column("porte", sa.String(length=2), nullable=True),
        sa.Column("capital_social", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("tipo_logradouro", sa.Text(), nullable=True),
        sa.Column("logradouro", sa.Text(), nullable=True),
        sa.Column("numero", sa.Text(), nullable=True),
        sa.Column("complemento", sa.Text(), nullable=True),
        sa.Column("bairro", sa.Text(), nullable=True),
        sa.Column("cep", sa.String(length=8), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("municipio_cod", sa.String(length=10), nullable=True),
        sa.Column("situacao_especial", sa.Text(), nullable=True),
        sa.Column("data_situacao_especial", sa.Date(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False,
                  server_default="receita_cnpj"),
        sa.Column("source_snapshot", sa.String(length=7), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_registry_staging_snapshot",
                    "registry_staging_companies", ["snapshot_id"])
    op.create_table(
        "registry_staging_company_cnaes",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("registry_snapshots.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("cnpj", sa.String(length=14), primary_key=True),
        sa.Column("cnae", sa.String(length=7), primary_key=True),
    )
    op.create_index("ix_registry_staging_cnaes_snapshot",
                    "registry_staging_company_cnaes", ["snapshot_id"])
    backfill(op.get_bind())


def downgrade() -> None:
    op.drop_index("ix_registry_staging_cnaes_snapshot",
                  table_name="registry_staging_company_cnaes")
    op.drop_table("registry_staging_company_cnaes")
    op.drop_index("ix_registry_staging_snapshot",
                  table_name="registry_staging_companies")
    op.drop_table("registry_staging_companies")
    op.drop_index("ix_registry_members_cnpj",
                  table_name="registry_snapshot_members")
    op.drop_index("ix_registry_members_snapshot",
                  table_name="registry_snapshot_members")
    op.drop_table("registry_snapshot_members")
    op.drop_index("uq_registry_snapshots_active_per_source",
                  table_name="registry_snapshots")
    op.drop_column("registry_snapshots", "is_active")
