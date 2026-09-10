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
    "organizations",
    "campaigns",
    "leads",
    "jobs",
    "lead_opportunities",
    "event_opportunities",
    "commercial_outcomes",
    "commercial_comparisons",
    "provider_execution_metrics",
    "company_aliases",
    "conversions",
    "follow_up_versions",
    "enrichments",
    "notifications",
    "persons",
    "decision_resolution_snapshots",
    "lead_opportunity_snapshots",
}
REQUIRED_INDEXES = {
    "ix_commercial_outcomes_org_offer",
    "ix_event_opportunities_org_date",
    "uq_event_opportunities_org_provider_identifier",
    "ix_commercial_comparisons_org_offer",
    "ix_provider_execution_metrics_org_recorded",
    "ix_provider_execution_metrics_org_provider",
    "ix_provider_execution_metrics_correlation",
    "ix_company_aliases_company",
    "ix_enrichments_lead_id",
    "ix_jobs_campaign_id",
    "ix_jobs_organization_id",
    "ix_jobs_pending_claim",
    "ix_leads_company_id",
    "ix_persons_organization_id",
    "ix_persons_company_id",
    "ix_event_opportunities_lead_id",
    "ix_commercial_outcomes_lead_id",
    "ix_notifications_lead_id",
    "ix_follow_up_versions_follow_up_id",
    "ix_decision_resolution_snapshots_org_lead",
    "ix_lead_opportunity_snapshots_org_lead",
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
    "decision_resolution_snapshots": {"organizations.id", "leads.id"},
    "provider_execution_metrics": {"organizations.id", "jobs.id", "campaigns.id"},
    "company_aliases": {"organizations.id", "companies.id"},
    "conversions": {"leads.id", "lead_opportunities.id"},
}
REQUIRED_UNIQUES = {
    "event_opportunities": {"uq_event_opportunities_org_source"},
    "commercial_outcomes": {"uq_commercial_outcomes_org_event"},
    "company_aliases": {"uq_company_aliases_org_kind_value"},
    "follow_up_versions": {"uq_follow_up_versions_follow_up_version"},
    "decision_resolution_snapshots": {"uq_decision_resolution_snapshot_hash"},
    "lead_opportunity_snapshots": {"uq_lead_opportunity_snapshot_hash"},
}
REQUIRED_COLUMNS = {
    "leads": {"discovery_provenance"},
    "provider_execution_metrics": {"correlation_id", "campaign_id", "usage"},
    "company_aliases": {"alias_kind", "alias_value"},
    "persons": {
        "identity_confidence",
        "contact_confidence",
        "source_reliability",
        "verification_status",
        "last_verified_at",
        "routability_type",
        "routable",
        "routability_reason",
    },
    "decision_resolution_snapshots": {
        "status",
        "snapshot_hash",
        "payload",
        "reason",
        "created_at",
    },
    "lead_opportunity_snapshots": {
        "offer_key",
        "offer_version",
        "formula_version",
        "score",
        "snapshot_hash",
        "reason",
        "created_at",
    },
}


def migration_head() -> str:
    script = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Esperado exatamente um head Alembic; encontrados: {heads}")
    return heads[0]


def verify_database(database_url: str) -> dict[str, object]:
    """Confirma revision, tabelas e índices essenciais de uma base existente."""
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
            indexes = {
                index["name"]
                for table in REQUIRED_TABLES & tables
                for index in database_inspector.get_indexes(table)
                if index.get("name")
            }
            missing_indexes = REQUIRED_INDEXES - indexes
            if missing_indexes:
                raise RuntimeError(f"Índices ausentes: {sorted(missing_indexes)}")
            missing_fks = {
                f"{table} -> {target}"
                for table, targets in REQUIRED_FKS.items()
                for target in targets
                if not any(
                    f"{foreign_key['referred_table']}.{column}"
                    == target
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
            missing_uniques = {
                name
                for names in REQUIRED_UNIQUES.values()
                for name in names
                if name not in uniques
            }
            if missing_uniques:
                raise RuntimeError(f"Constraints únicas ausentes: {sorted(missing_uniques)}")
            return {
                "revision": current,
                "tables": len(tables),
                "indexes_checked": len(REQUIRED_INDEXES),
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
        cwd=WORKERS_DIR,
        env=env,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"alembic upgrade head falhou ({completed.returncode})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.getenv("E2E_DATABASE_URL") or os.getenv("DATABASE_URL"),
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="aplica migrations pendentes antes da verificação",
    )
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("informe --database-url ou E2E_DATABASE_URL/DATABASE_URL")
    if args.upgrade:
        apply_upgrade(args.database_url)
    result = verify_database(args.database_url)
    print(
        f"Migrations OK: head={result['revision']} "
        f"tables={result['tables']} indexes={result['indexes_checked']} "
        f"fks={result['fks_checked']}"
        f" uniques={result['uniques_checked']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())