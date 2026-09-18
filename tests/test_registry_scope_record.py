"""Registro persistente do scope de importação (micro-PR F4).

Seams: `ImportScope.to_dict` (puro), `parse_manifest`/`dump_manifest`
(puro), `RegistryImporter` + `RegistrySnapshot.scope` (PG) e health (PG).
Um snapshot filtrado nunca deve parecer nacional no ledger, no health ou
na reprodução histórica.
"""
from __future__ import annotations

import os

import pytest

E2E_DATABASE_URL = os.environ.get("E2E_DATABASE_URL")
needs_pg = pytest.mark.skipif(not E2E_DATABASE_URL, reason="E2E_DATABASE_URL não definido")

SOURCE = "receita_cnpj"
MONTH = "2026-08"


def test_scope_to_dict_e_canonico():
    from services.registry.scope import parse_scope

    scope = parse_scope(ufs=["SP"], municipio_cods=["3503208"],
                        cnaes=["8650-0/03"], situacoes=["02"], matriz=True)
    assert scope is not None
    assert scope.to_dict() == {
        "ufs": ["SP"],
        "municipio_cods": ["3503208"],
        "cnaes": ["8650003"],
        "cnae_prefix_ranges": [],
        "situacoes": ["2"],
        "matriz": True,
    }


def test_manifest_aceita_scope_opcional_e_preserva_roundtrip():
    from services.registry.manifest import dump_manifest, load_manifest, parse_manifest
    import json

    base = {
        "manifest_version": "1",
        "source": "receita_cnpj",
        "snapshot_month": MONTH,
        "layout": "NOVOLAYOUTDOSDADOSABERTOSDOCNPJ",
        "layout_version": "2026-08",
        "encoding": "latin-1",
        "origin_kind": "receita_oficial",
        "origin_url": "https://arquivos.receitafederal.gov.br/dados/cnpj/2026-08",
        "accessed_at": "2026-09-01",
        "files": [{"table_kind": "estabelecimentos", "file_name": "ESTABELE0"}],
        "scope": {"ufs": ["SP"], "municipio_cods": ["3503208"]},
    }
    manifest = parse_manifest(base)
    assert manifest.scope == {"ufs": ["SP"], "municipio_cods": ["3503208"]}
    assert json.loads(dump_manifest(manifest))["scope"] == base["scope"]
    assert parse_manifest({k: v for k, v in base.items() if k != "scope"}).scope is None
    with pytest.raises(Exception, match="scope"):
        parse_manifest({**base, "scope": "SP"})


def _db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)()


def _cleanup(db):
    from database.models import (
        RegistryCompany,
        RegistryCompanyCnae,
        RegistrySnapshot,
    )

    db.query(RegistryCompanyCnae).filter(
        RegistryCompanyCnae.cnpj == "33000167000101").delete(
        synchronize_session=False)
    db.query(RegistryCompany).filter(
        RegistryCompany.cnpj == "33000167000101").delete(
        synchronize_session=False)
    snap = db.query(RegistrySnapshot).filter_by(
        source=SOURCE, snapshot_month=MONTH).first()
    if snap is not None:
        db.delete(snap)
    db.commit()


ESTAB = (
    '"33000167";"0001";"01";"1";"CLINICA";"02";"20200115";"00";"";"105";'
    '"20100110";"8650003";"";"RUA";"A";"10";"";"B";"14801770";"SP";"3503208";'
    '"21";"1";"";"";"";"";"";"";""'
)


@needs_pg
def test_import_persiste_scope_no_snapshot(tmp_path):
    from services.registry.importer import RegistryFileSpec, RegistryImporter
    from services.registry.scope import parse_scope

    engine, db = _db()
    try:
        festab = tmp_path / "ESTABELE0"
        festab.write_text(ESTAB, encoding="latin-1")
        scope = parse_scope(ufs=["SP"], municipio_cods=["3503208"],
                            cnaes=["8650-0/03"])
        snap = RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month=MONTH,
            files=[RegistryFileSpec(table_kind="estabelecimentos",
                                    path=str(festab), file_name="ESTABELE0")],
            scope=scope,
        )
        assert snap.status == "COMPLETED"
        assert snap.scope == scope.to_dict()

        from services.registry.activation import activate_snapshot

        activate_snapshot(db, source=SOURCE, snapshot_month=MONTH)
        db.expire_all()
        from database.models import RegistrySnapshot

        row = db.query(RegistrySnapshot).filter_by(
            source=SOURCE, snapshot_month=MONTH).one()
        assert row.scope == scope.to_dict()
        assert bool(row.is_active) is True
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


@needs_pg
def test_reimport_sem_scope_limpa_registro(tmp_path):
    from database.models import RegistrySnapshot
    from services.registry.importer import RegistryFileSpec, RegistryImporter
    from services.registry.scope import parse_scope

    engine, db = _db()
    try:
        festab = tmp_path / "ESTABELE0"
        festab.write_text(ESTAB, encoding="latin-1")
        scope = parse_scope(ufs=["SP"])
        RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month=MONTH,
            files=[RegistryFileSpec(table_kind="estabelecimentos",
                                    path=str(festab), file_name="ESTABELE0")],
            scope=scope,
        )
        snap = RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month=MONTH,
            files=[RegistryFileSpec(table_kind="estabelecimentos",
                                    path=str(festab), file_name="ESTABELE0")],
        )
        assert snap.scope is None
        db.expire_all()
        row = db.query(RegistrySnapshot).filter_by(
            source=SOURCE, snapshot_month=MONTH).one()
        assert row.scope is None
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


@needs_pg
def test_health_expoe_scope_do_ativo(tmp_path):
    from services.registry.activation import activate_snapshot
    from services.registry.importer import RegistryFileSpec, RegistryImporter
    from services.registry.scope import parse_scope
    from src.services.registry_health_service import RegistryHealthService

    engine, db = _db()
    try:
        festab = tmp_path / "ESTABELE0"
        festab.write_text(ESTAB, encoding="latin-1")
        scope = parse_scope(ufs=["SP"], municipio_cods=["3503208"],
                            cnaes=["8650-0/03"])
        RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month=MONTH,
            files=[RegistryFileSpec(table_kind="estabelecimentos",
                                    path=str(festab), file_name="ESTABELE0")],
            scope=scope,
        )
        activate_snapshot(db, source=SOURCE, snapshot_month=MONTH)
        health = RegistryHealthService(db).health()
        assert health["status"] == "healthy"
        assert health["companies"] == 1
        assert health["scope"] == scope.to_dict()
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()
