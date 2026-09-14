"""Cria o lifecycle tenant-scoped do Historical Importer.

A fila do import é própria porque jobs legados ainda podem ter
``organization_id`` nulo. O consumer falha fechado nesses jobs legados e
somente reivindica ImportJob com workspace obrigatório.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def _json_default() -> sa.TextClause:
    return sa.text("'[]'::jsonb")


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=True),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("source_format", sa.String(length=8), nullable=False),
        sa.Column("source_headers", postgresql.JSONB(), nullable=False),
        sa.Column("source_rows", postgresql.JSONB(), nullable=False),
        sa.Column("preview_rows", postgresql.JSONB(), server_default=_json_default(), nullable=False),
        sa.Column("mapping", postgresql.JSONB(), nullable=True),
        sa.Column("mapping_version", sa.String(length=64), nullable=True),
        sa.Column("dry_run_report", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("expected_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unprocessed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_import_jobs_org_idempotency"),
    )
    op.create_index("ix_import_jobs_org_status_created", "import_jobs", ["organization_id", "status", "created_at"])
    op.create_index("ix_import_jobs_org_source_hash", "import_jobs", ["organization_id", "source_hash"])

    op.create_table(
        "import_row_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("import_job_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason_code", sa.String(length=80), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("lead_id", sa.UUID(), nullable=True),
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("person_id", sa.UUID(), nullable=True),
        sa.Column("identity_decision", postgresql.JSONB(), nullable=True),
        sa.Column("provenance", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_job_id", "line_number", "source_version", name="uq_import_row_results_job_line_version"),
    )
    op.create_index("ix_import_row_results_job_status_line", "import_row_results", ["import_job_id", "status", "line_number"])

    op.create_table(
        "import_audit_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("import_job_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_audit_events_job_created", "import_audit_events", ["import_job_id", "created_at"])
    op.create_index("ix_import_audit_events_org_created", "import_audit_events", ["organization_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_import_audit_events_org_created", table_name="import_audit_events")
    op.drop_index("ix_import_audit_events_job_created", table_name="import_audit_events")
    op.drop_table("import_audit_events")
    op.drop_index("ix_import_row_results_job_status_line", table_name="import_row_results")
    op.drop_table("import_row_results")
    op.drop_index("ix_import_jobs_org_source_hash", table_name="import_jobs")
    op.drop_index("ix_import_jobs_org_status_created", table_name="import_jobs")
    op.drop_table("import_jobs")
