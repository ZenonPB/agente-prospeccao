"""Saúde da base de empresas (UX-3).

Seam: `summarize_registry_health` (puro, sem DB) + `RegistryHealthService`
(PG-gated). O endpoint só expõe o que o ledger realmente sabe: sem snapshot,
sem promessa.
"""
from __future__ import annotations

import os

import pytest

E2E_DATABASE_URL = os.environ.get("E2E_DATABASE_URL")
needs_pg = pytest.mark.skipif(not E2E_DATABASE_URL, reason="E2E_DATABASE_URL não definido")


def test_sem_snapshot_e_empty_sem_promessa():
    from src.services.registry_health_service import summarize_registry_health

    health = summarize_registry_health(
        latest=None, completed=None, companies=None, files=[])
    assert health["status"] == "empty"
    assert health["snapshot_month"] is None
    assert health["last_updated_at"] is None
    assert health["companies"] is None
    assert health["next_check"] is None


def test_snapshot_com_falha_e_degraded_com_erro_operacional():
    from src.services.registry_health_service import summarize_registry_health

    health = summarize_registry_health(
        latest={"snapshot_month": "2026-09", "status": "FAILED",
                "layout_version": None, "finished_at": None, "error": None},
        completed=None,
        companies=10,
        files=[{"file_name": "ESTABELE0", "table_kind": "estabelecimentos",
                "status": "FAILED", "rows_ok": 0, "rows_rejected": 0,
                "sha256": None, "error": "tamanho divergente"}],
    )
    assert health["status"] == "degraded"
    assert health["snapshot_month"] == "2026-09"
    assert health["companies"] == 10
    assert health["files"][0]["error"] == "tamanho divergente"


def test_snapshot_concluido_e_healthy_com_proveniencia():
    from src.services.registry_health_service import summarize_registry_health

    health = summarize_registry_health(
        latest={"snapshot_month": "2026-08", "status": "COMPLETED",
                "layout_version": "2026-08", "finished_at": "2026-09-01T10:00:00+00:00",
                "error": None},
        completed={"snapshot_month": "2026-08", "finished_at": "2026-09-01T10:00:00+00:00"},
        companies=3,
        files=[{"file_name": "ESTABELE0", "table_kind": "estabelecimentos",
                "status": "COMPLETED", "rows_ok": 3, "rows_rejected": 0,
                "sha256": "ab" * 32, "error": None}],
    )
    assert health["status"] == "healthy"
    assert health["last_updated_at"] == "2026-09-01T10:00:00+00:00"
    assert health["files"][0]["sha256"] == "ab" * 32


def test_snapshot_em_andamento_sem_concluido_e_unknown():
    from src.services.registry_health_service import summarize_registry_health

    health = summarize_registry_health(
        latest={"snapshot_month": "2026-09", "status": "RUNNING",
                "layout_version": None, "finished_at": None, "error": None},
        completed=None,
        companies=None,
        files=[],
    )
    assert health["status"] == "unknown"
    assert health["snapshot_month"] == "2026-09"


def _db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)()


@needs_pg
def test_service_deriva_estado_do_ledger_real():
    from database.models import RegistryCompany, RegistrySnapshot
    from src.services.registry_health_service import RegistryHealthService

    engine, db = _db()
    try:
        db.add(RegistrySnapshot(source="receita_cnpj", snapshot_month="2026-08",
                                status="COMPLETED"))
        db.add(RegistryCompany(cnpj="33000167000101", cnpj_basico="33000167",
                               source="receita_cnpj", source_snapshot="2026-08"))
        db.commit()
        health = RegistryHealthService(db).health()
        assert health["status"] == "healthy"
        assert health["snapshot_month"] == "2026-08"
        assert health["companies"] >= 1
    finally:
        row = db.query(RegistryCompany).filter_by(cnpj="33000167000101").first()
        if row is not None:
            db.delete(row)
        snap = db.query(RegistrySnapshot).filter_by(
            source="receita_cnpj", snapshot_month="2026-08").first()
        if snap is not None:
            db.delete(snap)
        db.commit()
        db.close()
        engine.dispose()
