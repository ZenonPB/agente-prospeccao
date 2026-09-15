"""Brazil Company Registry: universo empresarial global separado do CRM.

Revision ID: c1d2e3f4a5b6
Revises: fab1c2d3e4f5
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c1d2e3f4a5b6"
down_revision = "fab1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "registry_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="receita_cnpj"),
        sa.Column("snapshot_month", sa.String(length=7), nullable=False),
        sa.Column("layout_version", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="RUNNING"),
        sa.Column("processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parser_version", sa.String(length=20), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint("source", "snapshot_month", name="uq_registry_snapshots_source_month"),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_registry_snapshots_status",
        ),
    )
    op.create_table(
        "registry_import_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("registry_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("table_kind", sa.String(length=20), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_bytes", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("processed_lines", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rows_ok", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rows_rejected", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint("snapshot_id", "file_name", name="uq_registry_files_snapshot_name"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_registry_files_status",
        ),
        sa.CheckConstraint(
            "table_kind IN ('empresas', 'estabelecimentos', 'cnaes')",
            name="ck_registry_files_kind",
        ),
    )
    op.create_index("ix_registry_files_snapshot", "registry_import_files", ["snapshot_id"])
    op.create_table(
        "registry_companies",
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
        sa.Column("source", sa.String(length=40), nullable=False, server_default="receita_cnpj"),
        sa.Column("source_snapshot", sa.String(length=7), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()),
    )
    op.create_index("ix_registry_companies_basico", "registry_companies", ["cnpj_basico"])
    op.create_index("ix_registry_companies_cnae_uf", "registry_companies", ["cnae_principal", "uf", "cnpj"])
    op.create_index(
        "ix_registry_companies_geo", "registry_companies", ["uf", "municipio_cod", "situacao", "cnpj"]
    )
    op.create_table(
        "registry_company_cnaes",
        sa.Column("cnpj", sa.String(length=14), sa.ForeignKey("registry_companies.cnpj", ondelete="CASCADE"), primary_key=True),
        sa.Column("cnae", sa.String(length=7), primary_key=True),
    )
    op.create_index("ix_registry_cnaes_cnae", "registry_company_cnaes", ["cnae", "cnpj"])
    op.create_table(
        "registry_cnaes",
        sa.Column("codigo", sa.String(length=7), primary_key=True),
        sa.Column("descricao", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("registry_cnaes")
    op.drop_index("ix_registry_cnaes_cnae", table_name="registry_company_cnaes")
    op.drop_table("registry_company_cnaes")
    op.drop_index("ix_registry_companies_geo", table_name="registry_companies")
    op.drop_index("ix_registry_companies_cnae_uf", table_name="registry_companies")
    op.drop_index("ix_registry_companies_basico", table_name="registry_companies")
    op.drop_table("registry_companies")
    op.drop_index("ix_registry_files_snapshot", table_name="registry_import_files")
    op.drop_table("registry_import_files")
    op.drop_table("registry_snapshots")
