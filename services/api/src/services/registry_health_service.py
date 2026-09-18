"""Saúde da base de empresas: leitura read-only derivada do ledger real.

Expõe somente o que o ledger sabe: sem snapshot, sem promessa. Agregados
globais do universo empresarial (sem PII, sem dado de workspace).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any

# Garante que `services.*` dos workers resolva independente da ordem de import
# (padrão do repo; ver csv_import_service.py).
_workers_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "workers", "src")
if _workers_path not in sys.path:
    sys.path.insert(0, _workers_path)

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from services.registry.importer import SOURCE
from src.db.models import RegistryCompany, RegistryImportFile, RegistrySnapshot


def _iso(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return value if isinstance(value, str) else None


def summarize_registry_health(
    *, latest: dict | None, completed: dict | None,
    companies: int | None, files: list[dict],
) -> dict:
    """Monta a resposta a partir do estado do ledger (puro, sem DB)."""
    if latest is None:
        status = "empty"
    elif latest.get("status") == "FAILED":
        status = "degraded"
    elif latest.get("status") == "COMPLETED":
        status = "healthy"
    else:
        status = "unknown"
    finished = (completed or {}).get("finished_at")
    return {
        "status": status,
        "snapshot_month": (latest or {}).get("snapshot_month"),
        "layout_version": (latest or {}).get("layout_version"),
        "last_updated_at": _iso(finished),
        "companies": companies,
        "files": [
            {
                "file_name": entry.get("file_name"),
                "table_kind": entry.get("table_kind"),
                "status": entry.get("status"),
                "rows_ok": entry.get("rows_ok", 0),
                "rows_rejected": entry.get("rows_rejected", 0),
                "sha256": entry.get("sha256"),
                "error": str(entry.get("error") or "")[:300] or None,
            }
            for entry in files
        ],
        "next_check": None,
    }


class RegistryHealthService:
    """Deriva a saúde da base de `registry_snapshots`/`registry_import_files`."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def health(self) -> dict:
        db = self._db
        latest_row = (
            db.query(RegistrySnapshot)
            .filter(RegistrySnapshot.source == SOURCE)
            .order_by(desc(RegistrySnapshot.snapshot_month))
            .first()
        )
        if latest_row is None:
            return summarize_registry_health(
                latest=None, completed=None, companies=None, files=[])
        completed_row = (
            db.query(RegistrySnapshot)
            .filter(RegistrySnapshot.source == SOURCE,
                    RegistrySnapshot.status == "COMPLETED")
            .order_by(desc(RegistrySnapshot.snapshot_month))
            .first()
        )
        companies = db.query(func.count(RegistryCompany.cnpj)).scalar()
        file_rows = (
            db.query(RegistryImportFile)
            .filter(RegistryImportFile.snapshot_id == latest_row.id)
            .order_by(RegistryImportFile.file_name)
            .all()
        )
        return summarize_registry_health(
            latest={
                "snapshot_month": latest_row.snapshot_month,
                "status": latest_row.status,
                "layout_version": latest_row.layout_version,
                "finished_at": _iso(latest_row.finished_at),
                "error": latest_row.error,
            },
            completed=(
                {
                    "snapshot_month": completed_row.snapshot_month,
                    "finished_at": _iso(completed_row.finished_at),
                }
                if completed_row is not None else None
            ),
            companies=int(companies or 0),
            files=[
                {
                    "file_name": row.file_name,
                    "table_kind": row.table_kind,
                    "status": row.status,
                    "rows_ok": row.rows_ok,
                    "rows_rejected": row.rows_rejected,
                    "sha256": row.sha256,
                    "error": row.error,
                }
                for row in file_rows
            ],
        )
