"""Read-only certification harness for configured CRM connections.

This does not create/update CRM records. It validates authentication plus the
adapter's read contract and stores the evidence so production UAT can be run
with real workspace credentials without changing business data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from database.learning_models import CRMCertificationRun
from services.crm_adapters import CRM_ADAPTER_VERSION
from src.services.crm_sync_service import CRMSyncService


class CRMCertificationService:
    def __init__(self, db: Session, organization_id: Any):
        self.db = db
        self.organization_id = organization_id

    async def run(self, connection_id: Any, actor_id: Any = None) -> CRMCertificationRun:
        sync = CRMSyncService(self.db, self.organization_id)
        connection, adapter = await sync._adapter(connection_id)  # package seam; secret stays in memory
        checks: list[dict[str, Any]] = []
        overall = "PASSED"

        try:
            health = await adapter.healthcheck()
            health_status = str(health.get("status") or "unknown")
            checks.append({"name": "authentication", "status": "passed" if health_status == "ok" else "failed"})
            if health_status != "ok":
                overall = "FAILED"
        except Exception as exc:  # provider boundary: persist safe class only
            checks.append({"name": "authentication", "status": "failed", "error": type(exc).__name__})
            overall = "FAILED"

        if overall == "PASSED" and connection.provider == "salesforce":
            # Salesforce auth is genuinely exercised by /limits. Incremental
            # reads need tenant-specific SOQL/field mapping, so do not pretend an
            # empty local adapter response was a live remote read.
            checks.append({
                "name": "read_contract",
                "status": "not_applicable",
                "note": "autenticação real validada; leitura incremental exige SOQL configurado para o workspace",
            })
        elif overall == "PASSED":
            try:
                changes, _cursor = await adapter.fetch_changes(
                    organization_id=str(self.organization_id),
                    cursor=None,
                )
                checks.append({
                    "name": "read_contract",
                    "status": "passed",
                    "sample_count": min(len(changes), 100),
                    "note": "read-only; no cursor persisted",
                })
            except Exception as exc:
                checks.append({"name": "read_contract", "status": "failed", "error": type(exc).__name__})
                overall = "FAILED"

        row = CRMCertificationRun(
            organization_id=self.organization_id,
            connection_id=connection.id,
            provider=connection.provider,
            status=overall,
            checks=checks,
            adapter_version=CRM_ADAPTER_VERSION,
            tested_by_id=actor_id,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(row)
        connection.last_health_status = "ok" if overall == "PASSED" else "failed"
        connection.last_health_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_runs(self, connection_id: Any | None = None, limit: int = 50) -> list[CRMCertificationRun]:
        query = self.db.query(CRMCertificationRun).filter(
            CRMCertificationRun.organization_id == self.organization_id,
        )
        if connection_id is not None:
            query = query.filter(CRMCertificationRun.connection_id == connection_id)
        return query.order_by(CRMCertificationRun.created_at.desc()).limit(limit).all()
