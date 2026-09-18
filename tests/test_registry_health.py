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
        latest=None, completed=None, active=None,
        available_companies=None, files=[])
    assert health["status"] == "empty"
    assert health["snapshot_month"] is None
    assert health["last_updated_at"] is None
    assert health["companies"] is None
    assert health["active_snapshot_month"] is None
    assert health["last_attempt"] is None
    assert health["next_check"] is None


def test_ativo_com_falha_posterior_e_degraded_sem_misturar_tempo():
    from src.services.registry_health_service import summarize_registry_health

    health = summarize_registry_health(
        latest={"snapshot_month": "2026-09", "status": "FAILED",
                "layout_version": None, "finished_at": None, "error": "x"},
        completed={"snapshot_month": "2026-08", "status": "COMPLETED",
                   "layout_version": "2026-08",
                   "finished_at": "2026-09-01T10:00:00+00:00", "error": None},
        active={"snapshot_month": "2026-08", "status": "COMPLETED",
                "layout_version": "2026-08",
                "finished_at": "2026-09-01T10:00:00+00:00", "error": None},
        available_companies=10,
        files=[{"file_name": "ESTABELE0", "table_kind": "estabelecimentos",
                "status": "FAILED", "rows_ok": 0, "rows_rejected": 0,
                "sha256": None, "error": "tamanho divergente"}],
    )
    assert health["status"] == "degraded"
    # Servido (08), não a tentativa falha (09): sem finished_at alheio.
    assert health["snapshot_month"] == "2026-08"
    assert health["active_snapshot_month"] == "2026-08"
    assert health["last_updated_at"] == "2026-09-01T10:00:00+00:00"
    assert health["companies"] == 10
    assert health["last_attempt"] == {"snapshot_month": "2026-09", "status": "FAILED"}
    assert health["files"][0]["error"] == "tamanho divergente"


def test_snapshot_concluido_e_healthy_com_proveniencia():
    from src.services.registry_health_service import summarize_registry_health

    health = summarize_registry_health(
        latest={"snapshot_month": "2026-08", "status": "COMPLETED",
                "layout_version": "2026-08", "finished_at": "2026-09-01T10:00:00+00:00",
                "error": None},
        completed={"snapshot_month": "2026-08", "status": "COMPLETED",
                   "layout_version": "2026-08",
                   "finished_at": "2026-09-01T10:00:00+00:00", "error": None},
        active={"snapshot_month": "2026-08", "status": "COMPLETED",
                "layout_version": "2026-08",
                "finished_at": "2026-09-01T10:00:00+00:00", "error": None},
        available_companies=3,
        files=[{"file_name": "ESTABELE0", "table_kind": "estabelecimentos",
                "status": "COMPLETED", "rows_ok": 3, "rows_rejected": 0,
                "sha256": "ab" * 32, "error": None}],
    )
    assert health["status"] == "healthy"
    assert health["last_updated_at"] == "2026-09-01T10:00:00+00:00"
    assert health["files"][0]["sha256"] == "ab" * 32


def test_snapshot_em_andamento_sem_ativo_e_unknown():
    from src.services.registry_health_service import summarize_registry_health

    health = summarize_registry_health(
        latest={"snapshot_month": "2026-09", "status": "RUNNING",
                "layout_version": None, "finished_at": None, "error": None},
        completed=None,
        active=None,
        available_companies=None,
        files=[],
    )
    assert health["status"] == "unknown"
    assert health["companies"] is None
    assert health["active_snapshot_month"] is None
    assert health["last_attempt"] == {"snapshot_month": "2026-09", "status": "RUNNING"}


def _db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)()


def _cleanup(db, cnpjs=(), months=()):
    from database.models import RegistryCompany, RegistrySnapshot

    if cnpjs:
        for cnpj in cnpjs:
            row = db.query(RegistryCompany).filter_by(cnpj=cnpj).first()
            if row is not None:
                db.delete(row)
    for month in months:
        snap = db.query(RegistrySnapshot).filter_by(
            source="receita_cnpj", snapshot_month=month).first()
        if snap is not None:
            db.delete(snap)
    db.commit()


@needs_pg
def test_service_deriva_estado_do_ledger_real():
    from database.models import RegistryCompany, RegistrySnapshot
    from src.services.registry_health_service import RegistryHealthService

    from database.models import RegistrySnapshotMember

    engine, db = _db()
    try:
        snap = RegistrySnapshot(source="receita_cnpj", snapshot_month="2026-08",
                                status="COMPLETED", is_active=True)
        db.add(snap)
        db.flush()
        db.add(RegistryCompany(cnpj="33000167000101", cnpj_basico="33000167",
                               source="receita_cnpj", source_snapshot="2026-08"))
        db.add(RegistrySnapshotMember(snapshot_id=snap.id, cnpj="33000167000101"))
        db.commit()
        health = RegistryHealthService(db).health()
        assert health["status"] == "healthy"
        assert health["snapshot_month"] == "2026-08"
        assert health["companies"] >= 1
    finally:
        _cleanup(db, cnpjs=("33000167000101",), months=("2026-08",))
        db.close()
        engine.dispose()


@needs_pg
def test_companies_conta_apenas_membership_do_ativo():
    """AVAILABLE COMPANY: linhas fora do membership ACTIVE não contam."""
    from database.models import (
        RegistryCompany,
        RegistrySnapshot,
        RegistrySnapshotMember,
    )
    from src.services.registry_health_service import RegistryHealthService

    engine, db = _db()
    try:
        snap_a = RegistrySnapshot(source="receita_cnpj", snapshot_month="2026-08",
                                  status="COMPLETED", is_active=True)
        db.add(snap_a)
        db.add(RegistrySnapshot(source="receita_cnpj", snapshot_month="2026-09",
                                status="FAILED"))
        db.flush()
        db.add(RegistryCompany(cnpj="33000167000101", cnpj_basico="33000167",
                               source="receita_cnpj", source_snapshot="2026-08"))
        db.add(RegistryCompany(cnpj="33592510000154", cnpj_basico="33592510",
                               source="receita_cnpj", source_snapshot="2026-09"))
        db.add(RegistrySnapshotMember(snapshot_id=snap_a.id,
                                      cnpj="33000167000101"))
        db.commit()
        health = RegistryHealthService(db).health()
        assert health["companies"] == 1
        assert health["snapshot_month"] == "2026-08"
        assert health["active_snapshot_month"] == "2026-08"
        assert health["status"] == "degraded"
        assert health["last_attempt"] == {"snapshot_month": "2026-09",
                                         "status": "FAILED"}
    finally:
        _cleanup(db, cnpjs=("33000167000101", "33592510000154"),
                 months=("2026-08", "2026-09"))
        db.close()
        engine.dispose()


@needs_pg
def test_sem_ativo_e_unknown_com_companies_none():
    """Snapshots existem mas nada ACTIVE: sem contagem inventada."""
    from database.models import RegistryCompany, RegistrySnapshot
    from src.services.registry_health_service import RegistryHealthService

    engine, db = _db()
    try:
        db.add(RegistrySnapshot(source="receita_cnpj", snapshot_month="2026-09",
                                status="RUNNING"))
        db.add(RegistryCompany(cnpj="33000167000101", cnpj_basico="33000167",
                               source="receita_cnpj", source_snapshot="2026-09"))
        db.commit()
        health = RegistryHealthService(db).health()
        assert health["status"] == "unknown"
        assert health["companies"] is None
        assert health["active_snapshot_month"] is None
    finally:
        _cleanup(db, cnpjs=("33000167000101",), months=("2026-09",))
        db.close()
        engine.dispose()
