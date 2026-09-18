"""Verifica uma instalação Alembic sem alterar dados por padrão.

Uso, a partir da raiz do repositório:
    python scripts/verify_migrations.py --database-url "$E2E_DATABASE_URL"
    python scripts/verify_migrations.py --database-url "$E2E_DATABASE_URL" --upgrade

``--upgrade`` apenas aplica migrations pendentes no banco informado. O script
não cria banco, não faz downgrade e não executa autogenerate.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKERS_DIR = REPO_ROOT / "services" / "workers"
ALEMBIC_INI = WORKERS_DIR / "alembic.ini"
REQUIRED_TABLES = {
    "organizations", "campaigns", "leads", "jobs", "lead_opportunities",
    "event_opportunities", "commercial_outcomes", "commercial_comparisons",
    "provider_execution_metrics", "company_aliases", "conversions",
    "follow_up_versions", "enrichments", "notifications", "persons",
    "decision_resolution_snapshots", "lead_opportunity_snapshots",
    "controlled_learning_proposals", "login_attempts", "sequence_templates",
    "sequence_enrollments", "sequence_executions", "commercial_tasks",
    "next_best_action_decisions", "workflow_definitions", "workflow_runs",
    "offer_profile_versions", "offer_profile_activations", "crm_certification_runs",
    "lead_usefulness_feedbacks", "import_jobs", "import_row_results", "import_audit_events",
    "commercial_bulk_operations", "commercial_saved_views",
    "registry_snapshots", "registry_import_files", "registry_companies",
    "registry_company_cnaes", "registry_cnaes",
    "registry_snapshot_members", "registry_staging_companies",
    "registry_staging_company_cnaes",
}
REQUIRED_INDEXES = {
    "ix_commercial_outcomes_org_offer", "ix_event_opportunities_org_date",
    "uq_event_opportunities_org_provider_identifier", "ix_commercial_comparisons_org_offer",
    "ix_provider_execution_metrics_org_recorded", "ix_provider_execution_metrics_org_provider",
    "ix_provider_execution_metrics_correlation", "ix_company_aliases_company",
    "ix_enrichments_lead_id", "ix_jobs_campaign_id", "ix_jobs_organization_id",
    "ix_jobs_pending_claim", "ix_leads_company_id", "ix_persons_organization_id",
    "ix_persons_company_id", "ix_persons_org_document_cpf", "ix_persons_org_email",
    "ix_event_opportunities_lead_id",
    "ix_commercial_outcomes_lead_id", "ix_notifications_lead_id",
    "ix_follow_up_versions_follow_up_id", "ix_decision_resolution_snapshots_org_lead",
    "ix_lead_opportunity_snapshots_org_lead", "ix_controlled_learning_org_offer_status",
    "ix_sequence_templates_org_enabled", "ix_sequence_enrollments_org_status_next",
    "ix_sequence_enrollments_lead", "ix_sequence_executions_org_status_scheduled",
    "ix_commercial_tasks_org_status_due", "ix_commercial_tasks_owner_status",
    "ix_commercial_tasks_lead", "ix_nba_decisions_org_lead_created",
    "ix_nba_decisions_org_status_deadline", "ix_workflow_definitions_org_trigger_enabled",
    "ix_workflow_runs_org_status_started", "ix_offer_profile_versions_org_offer_active",
    "uq_offer_profile_versions_one_active", "ix_offer_profile_activations_org_offer_created",
    "ix_crm_certification_org_connection_created",
    "ix_lead_usefulness_org_created", "ix_lead_usefulness_lead_id",
    "ix_commercial_bulk_operations_org_created", "ix_commercial_saved_views_org_kind",
    "ix_import_jobs_org_status_created", "ix_import_jobs_org_source_hash",
    "ix_import_row_results_job_status_line", "ix_import_audit_events_job_created", "ix_import_audit_events_org_created",
    "uq_conversions_lead_offer",
    "ix_registry_companies_basico", "ix_registry_companies_cnae_uf", "ix_registry_companies_geo",
    "ix_registry_cnaes_cnae", "ix_registry_files_snapshot",
    "ix_registry_members_snapshot", "ix_registry_members_cnpj",
    "ix_registry_staging_snapshot", "ix_registry_staging_cnaes_snapshot",
    "uq_registry_snapshots_active_per_source",
}
REQUIRED_UNIQUE_INDEXES = {
    "conversions": {"uq_conversions_lead_offer"},
    "registry_snapshots": {"uq_registry_snapshots_active_per_source"},
}
REQUIRED_CHECK_CONSTRAINTS = {
    "jobs": {"ck_jobs_organization_required"},
    "leads": {"ck_leads_lost_reason_required"},
    "registry_snapshots": {"ck_registry_snapshots_status"},
    "registry_import_files": {"ck_registry_files_status", "ck_registry_files_kind"},
}
REQUIRED_NOT_NULL_COLUMNS = {
    "jobs": {"organization_id"},
}
REQUIRED_FKS = {
    "campaigns": {"organizations.id"},
    "leads": {"organizations.id"},
    "jobs": {"organizations.id"},
    "lead_opportunities": {"organizations.id", "leads.id"},
    "lead_opportunity_snapshots": {"organizations.id", "leads.id", "lead_opportunities.id"},
    "event_opportunities": {"organizations.id", "leads.id", "contacts.id"},
    "commercial_outcomes": {"organizations.id", "leads.id"},
    "commercial_comparisons": {"organizations.id", "users.id"},
    "controlled_learning_proposals": {"organizations.id", "commercial_comparisons.id", "users.id"},
    "decision_resolution_snapshots": {"organizations.id", "leads.id"},
    "provider_execution_metrics": {"organizations.id", "jobs.id", "campaigns.id"},
    "company_aliases": {"organizations.id", "companies.id"},
    "conversions": {"leads.id", "lead_opportunities.id"},
    "sequence_templates": {"organizations.id", "users.id"},
    "sequence_enrollments": {"organizations.id", "sequence_templates.id", "leads.id", "persons.id", "users.id"},
    "sequence_executions": {"organizations.id", "sequence_enrollments.id", "leads.id"},
    "commercial_tasks": {"organizations.id", "leads.id", "persons.id", "sequence_enrollments.id", "users.id"},
    "next_best_action_decisions": {"organizations.id", "leads.id", "sequence_enrollments.id"},
    "workflow_definitions": {"organizations.id", "users.id"},
    "workflow_runs": {"organizations.id", "workflow_definitions.id"},
    "offer_profile_versions": {"organizations.id", "controlled_learning_proposals.id", "offer_profile_versions.id", "users.id"},
    "offer_profile_activations": {"organizations.id", "offer_profile_versions.id", "users.id"},
    "crm_certification_runs": {"organizations.id", "crm_connections.id", "users.id"},
    "lead_usefulness_feedbacks": {"organizations.id", "leads.id", "users.id"},
    "import_jobs": {"organizations.id", "campaigns.id", "users.id"},
    "import_row_results": {"import_jobs.id", "organizations.id", "leads.id", "companies.id", "persons.id"},
    "import_audit_events": {"import_jobs.id", "organizations.id", "users.id"},
    "commercial_bulk_operations": {"organizations.id", "users.id"},
    "commercial_saved_views": {"organizations.id", "users.id"},
    "registry_import_files": {"registry_snapshots.id"},
    "registry_company_cnaes": {"registry_companies.cnpj"},
    "registry_snapshot_members": {"registry_snapshots.id"},
    "registry_staging_companies": {"registry_snapshots.id"},
    "registry_staging_company_cnaes": {"registry_snapshots.id"},
}
REQUIRED_UNIQUES = {
    "event_opportunities": {"uq_event_opportunities_org_source"},
    "commercial_outcomes": {"uq_commercial_outcomes_org_event"},
    "company_aliases": {"uq_company_aliases_org_kind_value"},
    "follow_up_versions": {"uq_follow_up_versions_follow_up_version"},
    "decision_resolution_snapshots": {"uq_decision_resolution_snapshot_hash"},
    "lead_opportunity_snapshots": {"uq_lead_opportunity_snapshot_hash"},
    "controlled_learning_proposals": {"uq_controlled_learning_org_comparison", "uq_controlled_learning_org_offer_version"},
    "sequence_templates": {"uq_sequence_templates_org_name_version"},
    "sequence_enrollments": {"uq_sequence_enrollments_sequence_lead"},
    "sequence_executions": {"uq_sequence_executions_enrollment_step", "uq_sequence_executions_org_idempotency"},
    "commercial_tasks": {"uq_commercial_tasks_org_idempotency"},
    "next_best_action_decisions": {"uq_nba_decisions_org_lead_fingerprint"},
    "workflow_definitions": {"uq_workflow_definitions_org_name_version"},
    "workflow_runs": {"uq_workflow_runs_org_workflow_event"},
    "offer_profile_versions": {"uq_offer_profile_versions_org_offer_version"},
    "lead_usefulness_feedbacks": {"uq_lead_usefulness_lead_user"},
    "import_jobs": {"uq_import_jobs_org_idempotency"},
    "commercial_bulk_operations": {"uq_commercial_bulk_operations_org_idempotency"},
    "commercial_saved_views": {"uq_commercial_saved_views_owner_name"},
    "import_row_results": {"uq_import_row_results_job_line_version"},
    "registry_snapshots": {"uq_registry_snapshots_source_month"},
    "registry_import_files": {"uq_registry_files_snapshot_name"},
}
REQUIRED_COLUMNS = {
    "leads": {"discovery_provenance"},
    "provider_execution_metrics": {"correlation_id", "campaign_id", "usage"},
    "company_aliases": {"alias_kind", "alias_value"},
    "persons": {"identity_confidence", "contact_confidence", "source_reliability", "verification_status", "last_verified_at", "routability_type", "routable", "routability_reason"},
    "decision_resolution_snapshots": {"status", "snapshot_hash", "payload", "reason", "created_at"},
    "lead_opportunity_snapshots": {"offer_key", "offer_version", "formula_version", "score", "snapshot_hash", "reason", "created_at"},
    "lead_opportunities": {"score_breakdown"},
    "controlled_learning_proposals": {"proposal_version", "status", "evidence_snapshot", "published_at", "created_at"},
    "sequence_templates": {"steps", "version", "persona_key", "offer_key", "enabled"},
    "sequence_enrollments": {"status", "current_step_index", "next_action_at", "pause_reason"},
    "sequence_executions": {"step_type", "status", "scheduled_at", "idempotency_key", "payload"},
    "commercial_tasks": {"task_type", "status", "due_at", "idempotency_key", "source"},
    "next_best_action_decisions": {"action", "why", "confidence", "evidence", "deadline", "fingerprint"},
    "workflow_definitions": {"trigger_type", "conditions", "actions", "version", "enabled"},
    "workflow_runs": {"event_key", "status", "context", "action_results", "started_at"},
    "offer_profile_versions": {"offer_key", "version", "profile_snapshot", "is_active", "source_proposal_id", "activated_at", "deactivated_at"},
    "offer_profile_activations": {"offer_key", "action", "version_id", "previous_version_id", "actor_id", "created_at"},
    "crm_certification_runs": {"provider", "status", "checks", "adapter_version", "tested_by_id", "created_at"},
    "lead_usefulness_feedbacks": {"useful", "reason", "detail", "campaign_id", "created_at"},
    "import_jobs": {"organization_id", "source_hash", "idempotency_key", "source_headers", "source_rows", "mapping", "mapping_version", "dry_run_report", "status", "expected_version", "confirm_base_version", "confirm_xid", "accepted_rows", "duplicate_rows", "rejected_rows", "failed_rows", "unprocessed_rows"},
    "import_row_results": {"import_job_id", "organization_id", "line_number", "source_version", "status", "reason_code", "identity_decision", "provenance"},
    "import_audit_events": {"import_job_id", "organization_id", "action", "from_status", "to_status", "correlation_id", "created_at"},
    "commercial_bulk_operations": {"organization_id", "actor_id", "idempotency_key", "operation", "payload_hash", "status", "result", "created_at", "completed_at"},
    "commercial_saved_views": {"organization_id", "owner_user_id", "name", "view_kind", "filters", "shared", "created_at", "updated_at"},
    "registry_snapshots": {"source", "snapshot_month", "status", "is_active", "scope", "processed", "inserted", "updated", "unchanged", "rejected", "failed"},
    "registry_import_files": {"snapshot_id", "table_kind", "file_name", "status", "processed_lines", "sha256"},
    "registry_companies": {"cnpj", "cnpj_basico", "content_hash", "source", "source_snapshot"},
}


def migration_head() -> str:
    script = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Esperado exatamente um head Alembic; encontrados: {heads}")
    return heads[0]


def verify_database(database_url: str) -> dict[str, object]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
            expected = migration_head()
            if current != expected:
                raise RuntimeError(f"Banco em {current!r}; esperado {expected!r}")
            database_inspector = inspect(connection)
            tables = set(database_inspector.get_table_names())
            missing_tables = REQUIRED_TABLES - tables
            if missing_tables:
                raise RuntimeError(f"Tabelas ausentes: {sorted(missing_tables)}")
            get_columns = getattr(database_inspector, "get_columns", None)
            missing_columns = set()
            if get_columns is not None:
                missing_columns = {
                    f"{table}.{column}"
                    for table, columns in REQUIRED_COLUMNS.items()
                    for column in columns
                    if column not in {item["name"] for item in get_columns(table)}
                }
            if missing_columns:
                raise RuntimeError(f"Colunas essenciais ausentes: {sorted(missing_columns)}")
            if get_columns is not None:
                missing_not_null = {
                    f"{table}.{column}"
                    for table, columns in REQUIRED_NOT_NULL_COLUMNS.items()
                    for column in columns
                    if next(
                        item for item in get_columns(table) if item["name"] == column
                    ).get("nullable", True)
                }
                if missing_not_null:
                    raise RuntimeError(
                        f"Colunas que deveriam ser NOT NULL: {sorted(missing_not_null)}"
                    )
            indexes_by_table = {
                table: {
                    index["name"]: index
                    for index in database_inspector.get_indexes(table)
                    if index.get("name")
                }
                for table in REQUIRED_TABLES & tables
            }
            indexes = set().union(*(set(items) for items in indexes_by_table.values()))
            missing_indexes = REQUIRED_INDEXES - indexes
            if missing_indexes:
                raise RuntimeError(f"Índices ausentes: {sorted(missing_indexes)}")
            non_unique_indexes = {
                f"{table}.{name}"
                for table, names in REQUIRED_UNIQUE_INDEXES.items()
                for name in names
                if not indexes_by_table.get(table, {}).get(name, {}).get("unique", False)
            }
            if non_unique_indexes:
                raise RuntimeError(
                    f"Índices únicos ausentes ou não únicos: {sorted(non_unique_indexes)}"
                )
            get_check_constraints = getattr(database_inspector, "get_check_constraints", None)
            if get_check_constraints is None:
                raise RuntimeError("Inspector não expõe check constraints obrigatórias")
            missing_checks = {
                f"{table}.{name}"
                for table, names in REQUIRED_CHECK_CONSTRAINTS.items()
                for name in names
                if name not in {
                    constraint.get("name")
                    for constraint in get_check_constraints(table)
                    if constraint.get("name")
                }
            }
            if missing_checks:
                raise RuntimeError(f"Checks obrigatórios ausentes: {sorted(missing_checks)}")
            missing_fks = {
                f"{table} -> {target}"
                for table, targets in REQUIRED_FKS.items()
                for target in targets
                if not any(
                    f"{foreign_key['referred_table']}.{column}" == target
                    for foreign_key in database_inspector.get_foreign_keys(table)
                    for column in foreign_key.get("referred_columns", [])
                )
            }
            if missing_fks:
                raise RuntimeError(f"FKs ausentes: {sorted(missing_fks)}")
            uniques = {
                constraint["name"]
                for table in REQUIRED_UNIQUES
                for constraint in database_inspector.get_unique_constraints(table)
                if constraint.get("name")
            }
            missing_uniques = {name for names in REQUIRED_UNIQUES.values() for name in names if name not in uniques}
            if missing_uniques:
                raise RuntimeError(f"Constraints únicas ausentes: {sorted(missing_uniques)}")
            return {
                "revision": current,
                "tables": len(tables),
                "indexes_checked": len(REQUIRED_INDEXES),
                "unique_indexes_checked": sum(len(names) for names in REQUIRED_UNIQUE_INDEXES.values()),
                "checks_checked": sum(len(names) for names in REQUIRED_CHECK_CONSTRAINTS.values()),
                "not_null_columns_checked": sum(len(columns) for columns in REQUIRED_NOT_NULL_COLUMNS.values()),
                "fks_checked": sum(len(targets) for targets in REQUIRED_FKS.values()),
                "uniques_checked": sum(len(names) for names in REQUIRED_UNIQUES.values()),
            }
    finally:
        engine.dispose()


def apply_upgrade(database_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=WORKERS_DIR, env=env, check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"alembic upgrade head falhou ({completed.returncode})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("E2E_DATABASE_URL") or os.getenv("DATABASE_URL"))
    parser.add_argument("--upgrade", action="store_true", help="aplica migrations pendentes antes da verificação")
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("informe --database-url ou E2E_DATABASE_URL/DATABASE_URL")
    if args.upgrade:
        apply_upgrade(args.database_url)
    result = verify_database(args.database_url)
    print(
        f"Migrations OK: head={result['revision']} tables={result['tables']} "
        f"indexes={result['indexes_checked']} fks={result['fks_checked']} uniques={result['uniques_checked']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())