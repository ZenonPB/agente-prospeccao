"""Saúde da base de empresas: leitura read-only derivada do ledger real.

Semântica temporal explícita (quatro conceitos distintos):
- latest: última tentativa (qualquer status);
- completed: último COMPLETED (elegível, ainda invisível);
- active: snapshot ACTIVE servido pela descoberta (0 ou 1 por source);
- available: membership do ACTIVE (AVAILABLE COMPANY, mesma regra da busca).

`companies` conta APENAS o membership do ACTIVE (None quando não há ACTIVE).
`snapshot_month`/`last_updated_at` refletem o que está SERVIDO, não a última
tentativa; a tentativa aparece separada em `last_attempt`. Status:
empty (sem ledger), unknown (ledger sem ACTIVE servível), degraded (ACTIVE
serve mas a última tentativa falhou), healthy (ACTIVE serve e a última
tentativa é o próprio ativo).
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

from sqlalchemy import desc
from sqlalchemy.orm import Session

from services.registry.availability import available_company_count
from services.registry.importer import SOURCE
from src.db.models import RegistryImportFile, RegistrySnapshot


def _iso(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return value if isinstance(value, str) else None


def summarize_registry_health(
    *, latest: dict | None, completed: dict | None, active: dict | None,
    available_companies: int | None, files: list[dict],
) -> dict:
    """Monta a resposta a partir do estado do ledger (puro, sem DB)."""
    if latest is None:
        status = "empty"
    elif active is None:
        status = "unknown"
    elif latest.get("status") == "FAILED":
        status = "degraded"
    else:
        status = "healthy"
    served = active or completed
    return {
        "status": status,
        "snapshot_month": (served or {}).get("snapshot_month"),
        "layout_version": (served or {}).get("layout_version"),
        "last_updated_at": _iso((served or {}).get("finished_at")),
        "companies": available_companies,
        "active_snapshot_month": (active or {}).get("snapshot_month"),
        "last_attempt": (
            {"snapshot_month": latest.get("snapshot_month"),
             "status": latest.get("status")}
            if latest is not None else None
        ),
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


def _row_dict(row: Any) -> dict:
    return {
        "snapshot_month": row.snapshot_month,
        "status": row.status,
        "layout_version": row.layout_version,
        "finished_at": _iso(row.finished_at),
        "error": row.error,
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
                latest=None, completed=None, active=None,
                available_companies=None, files=[])
        completed_row = (
            db.query(RegistrySnapshot)
            .filter(RegistrySnapshot.source == SOURCE,
                    RegistrySnapshot.status == "COMPLETED")
            .order_by(desc(RegistrySnapshot.snapshot_month))
            .first()
        )
        active_row = (
            db.query(RegistrySnapshot)
            .filter(RegistrySnapshot.source == SOURCE,
                    RegistrySnapshot.is_active.is_(True))
            .one_or_none()
        )
        available = (
            available_company_count(db, active_row.id)
            if active_row is not None else None
        )
        file_rows = (
            db.query(RegistryImportFile)
            .filter(RegistryImportFile.snapshot_id == latest_row.id)
            .order_by(RegistryImportFile.file_name)
            .all()
        )
        return summarize_registry_health(
            latest=_row_dict(latest_row),
            completed=_row_dict(completed_row) if completed_row is not None else None,
            active=_row_dict(active_row) if active_row is not None else None,
            available_companies=available,
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
