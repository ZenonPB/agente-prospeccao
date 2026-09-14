"""Schema gate adicional do Sales Operating System (Bloco B)."""
from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine, inspect

REQUIRED = {
    "commercial_saved_views": {
        "columns": {"organization_id", "owner_user_id", "name", "view_kind", "filters", "shared", "created_at", "updated_at"},
        "uniques": {"uq_commercial_saved_views_owner_name"},
        "indexes": {"ix_commercial_saved_views_org_kind"},
        "fks": {"organizations.id", "users.id"},
    },
    "lead_crm_metadata": {
        "columns": {"organization_id", "lead_id", "tags", "archived_at", "archived_by_id", "created_at", "updated_at"},
        "uniques": {"uq_lead_crm_metadata_lead"},
        "indexes": {"ix_lead_crm_metadata_org_archived"},
        "fks": {"organizations.id", "leads.id", "users.id"},
    },
    "crm_entity_audit": {
        "columns": {"organization_id", "actor_id", "entity_type", "entity_id", "action", "changes", "created_at"},
        "uniques": set(),
        "indexes": {"ix_crm_entity_audit_org_entity"},
        "fks": {"organizations.id", "users.id"},
    },
}


def verify(database_url: str) -> dict[str, int]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            tables = set(inspector.get_table_names())
            missing_tables = set(REQUIRED) - tables
            if missing_tables:
                raise RuntimeError(f"Tabelas Bloco B ausentes: {sorted(missing_tables)}")
            for table, contract in REQUIRED.items():
                columns = {item["name"] for item in inspector.get_columns(table)}
                missing_columns = contract["columns"] - columns
                if missing_columns:
                    raise RuntimeError(f"Colunas ausentes em {table}: {sorted(missing_columns)}")
                indexes = {item["name"] for item in inspector.get_indexes(table) if item.get("name")}
                missing_indexes = contract["indexes"] - indexes
                if missing_indexes:
                    raise RuntimeError(f"Índices ausentes em {table}: {sorted(missing_indexes)}")
                uniques = {item["name"] for item in inspector.get_unique_constraints(table) if item.get("name")}
                missing_uniques = contract["uniques"] - uniques
                if missing_uniques:
                    raise RuntimeError(f"Uniques ausentes em {table}: {sorted(missing_uniques)}")
                fks = {
                    f"{item['referred_table']}.{column}"
                    for item in inspector.get_foreign_keys(table)
                    for column in item.get("referred_columns", [])
                }
                missing_fks = contract["fks"] - fks
                if missing_fks:
                    raise RuntimeError(f"FKs ausentes em {table}: {sorted(missing_fks)}")
            return {"tables": len(REQUIRED), "contracts": sum(len(v["columns"]) for v in REQUIRED.values())}
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("E2E_DATABASE_URL") or os.getenv("DATABASE_URL"))
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("informe --database-url ou E2E_DATABASE_URL/DATABASE_URL")
    result = verify(args.database_url)
    print(f"Sales Operating schema OK: tables={result['tables']} contracts={result['contracts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
