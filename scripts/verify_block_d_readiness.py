#!/usr/bin/env python3
"""Verifier fail-closed do Bloco D para PostgreSQL real.

Não lê nem imprime secrets. Falha se tabelas canônicas tiverem linhas órfãs de
workspace ou se houver mais de uma OfferProfileVersion ativa por oferta/tenant.
"""
from __future__ import annotations

import argparse
import json
from sqlalchemy import create_engine, inspect, text


TENANT_TABLES = (
    "campaigns",
    "leads",
    "lead_opportunities",
    "commercial_outcomes",
    "jobs",
)


def verify(database_url: str) -> dict:
    engine = create_engine(database_url)
    problems: list[str] = []
    evidence: dict[str, object] = {}
    with engine.connect() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        for table in TENANT_TABLES:
            if table not in tables:
                continue
            columns = {col["name"] for col in inspector.get_columns(table)}
            if "organization_id" not in columns:
                problems.append(f"{table}: sem organization_id")
                continue
            orphan_count = conn.execute(text(f'SELECT COUNT(*) FROM "{table}" WHERE organization_id IS NULL')).scalar_one()
            evidence[f"{table}.orphan_count"] = int(orphan_count)
            if orphan_count:
                problems.append(f"{table}: {orphan_count} registro(s) órfão(s)")

        if "offer_profile_versions" in tables:
            duplicates = conn.execute(text("""
                SELECT organization_id, offer_key, COUNT(*)
                FROM offer_profile_versions
                WHERE is_active IS TRUE
                GROUP BY organization_id, offer_key
                HAVING COUNT(*) > 1
            """)).all()
            evidence["offer_profile_versions.multiple_active"] = len(duplicates)
            if duplicates:
                problems.append("offer_profile_versions: múltiplas versões ativas no mesmo tenant/oferta")

        if "alembic_version" not in tables:
            problems.append("alembic_version ausente")
        else:
            heads = conn.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar_one()
            evidence["alembic_heads"] = int(heads)
            if heads != 1:
                problems.append(f"esperada uma cabeça Alembic, encontradas {heads}")

    return {"status": "READY" if not problems else "BLOCKED", "problems": problems, "evidence": evidence}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()
    result = verify(args.database_url)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
