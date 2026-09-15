"""Ingestão do Registry em PG real: idempotência, resume, contadores, erros.

Pula sem E2E_DATABASE_URL. Fixtures sintéticas fiéis ao layout oficial.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

E2E_DATABASE_URL = os.environ.get("E2E_DATABASE_URL")
pytestmark = pytest.mark.skipif(not E2E_DATABASE_URL, reason="E2E_DATABASE_URL não definido")


def _db():
    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)()


def _estab(basico, ordem, dv, fantasia="X", sit="2", cnae="6000001", uf="RJ", mun="6001"):
    cols = [basico, ordem, dv, "1" if ordem == "0001" else "2", fantasia, sit,
            "20200115", "00", "", "105", "20100110", cnae, "", "RUA", "A",
            "10", "", "B", "20031170", uf, mun,
            "21", "1", "", "", "", "", "", "", ""]
    assert len(cols) == 30
    return ";".join(f'"{c}"' for c in cols)


def test_first_import_inserts_and_completes(tmp_path):
    from services.registry.importer import RegistryFileSpec, RegistryImporter

    engine, db = _db()
    try:
        f = tmp_path / "ESTABELE0"
        f.write_text("\n".join([
            _estab("33000167", "0001", "01", fantasia="PETROBRAS"),
            _estab("33592510", "0001", "54", fantasia="VALE", uf="RJ"),
        ]), encoding="latin-1")
        imp = RegistryImporter(db, batch_size=10)
        snap = imp.import_snapshot(
            snapshot_month="2026-08",
            files=[RegistryFileSpec(table_kind="estabelecimentos", path=str(f), file_name="ESTABELE0")],
        )
        assert snap.status == "COMPLETED"
        assert snap.processed == 2
        assert snap.inserted == 2
        assert snap.updated == 0
        assert snap.rejected == 0
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_identical_reimport_is_skipped(tmp_path):
    from services.registry.importer import RegistryFileSpec, RegistryImporter

    engine, db = _db()
    try:
        f = tmp_path / "ESTABELE0"
        f.write_text(_estab("33000167", "0001", "01"), encoding="latin-1")
        spec = [RegistryFileSpec(table_kind="estabelecimentos", path=str(f), file_name="ESTABELE0")]
        first = RegistryImporter(db, batch_size=10).import_snapshot(snapshot_month="2026-08", files=spec)
        assert first.inserted == 1
        second = RegistryImporter(db, batch_size=10).import_snapshot(snapshot_month="2026-08", files=spec)
        assert second.status == "COMPLETED"
        assert second.processed == 0
        assert second.inserted == 0
        assert second.updated == 0
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_same_content_new_bytes_counts_as_unchanged(tmp_path):
    from services.registry.importer import RegistryFileSpec, RegistryImporter

    engine, db = _db()
    try:
        f = tmp_path / "ESTABELE0"
        f.write_text(_estab("33000167", "0001", "01"), encoding="latin-1")
        spec = [RegistryFileSpec(table_kind="estabelecimentos", path=str(f), file_name="ESTABELE0")]
        RegistryImporter(db, batch_size=10).import_snapshot(snapshot_month="2026-08", files=spec)
        f.write_text(_estab("33000167", "0001", "01") + "\n", encoding="latin-1")
        second = RegistryImporter(db, batch_size=10).import_snapshot(snapshot_month="2026-08", files=spec)
        assert second.processed == 1
        assert second.inserted == 0
        assert second.updated == 0
        assert second.unchanged == 1
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_changed_row_counts_as_updated(tmp_path):
    from services.registry.importer import RegistryFileSpec, RegistryImporter

    engine, db = _db()
    try:
        f = tmp_path / "ESTABELE0"
        f.write_text(_estab("33000167", "0001", "01", fantasia="NOME A"), encoding="latin-1")
        spec = [RegistryFileSpec(table_kind="estabelecimentos", path=str(f), file_name="ESTABELE0")]
        RegistryImporter(db, batch_size=10).import_snapshot(snapshot_month="2026-08", files=spec)
        f.write_text(_estab("33000167", "0001", "01", fantasia="NOME BEM MAIOR"), encoding="latin-1")
        # tamanho muda para forçar reprocessamento em vez do fast-path skip
        second = RegistryImporter(db, batch_size=10).import_snapshot(snapshot_month="2026-08", files=spec)
        assert second.updated == 1
        assert second.unchanged == 0
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_bad_rows_are_rejected_without_aborting(tmp_path):
    from services.registry.importer import RegistryFileSpec, RegistryImporter

    engine, db = _db()
    try:
        f = tmp_path / "ESTABELE0"
        f.write_text("\n".join([
            _estab("33000167", "0001", "01"),
            '"curta";"demais"',
            _estab("33592510", "0001", "54"),
        ]), encoding="latin-1")
        snap = RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month="2026-08",
            files=[RegistryFileSpec(table_kind="estabelecimentos", path=str(f), file_name="ESTABELE0")],
        )
        assert snap.status == "COMPLETED"
        assert snap.processed == 2
        assert snap.rejected == 1
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_missing_file_fails_closed(tmp_path):
    from services.registry.importer import RegistryFileSpec, RegistryImporter

    engine, db = _db()
    try:
        snap = RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month="2026-08",
            files=[RegistryFileSpec(table_kind="estabelecimentos",
                                    path=str(tmp_path / "AUSENTE"), file_name="AUSENTE")],
        )
        assert snap.status == "FAILED"
        assert snap.failed >= 1
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_resume_continues_from_checkpoint(tmp_path):
    from database.models import RegistryCompany, RegistryImportFile, RegistrySnapshot
    from services.registry.importer import RegistryFileSpec, RegistryImporter

    engine, db = _db()
    try:
        f = tmp_path / "ESTABELE0"
        f.write_text("\n".join([
            _estab("33000167", "0001", "01"),
            _estab("33592510", "0001", "54"),
        ]), encoding="latin-1")
        snap = RegistrySnapshot(source="receita_cnpj", snapshot_month="2026-08", status="RUNNING")
        db.add(snap)
        db.flush()
        db.add(RegistryImportFile(
            snapshot_id=snap.id, table_kind="estabelecimentos",
            file_name="ESTABELE0", status="RUNNING", processed_lines=1,
        ))
        db.commit()
        result = RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month="2026-08",
            files=[RegistryFileSpec(table_kind="estabelecimentos", path=str(f), file_name="ESTABELE0")],
        )
        assert result.status == "COMPLETED"
        assert result.processed == 1
        db.expire_all()
        assert db.query(RegistryCompany).filter(
            RegistryCompany.cnpj == "33592510000154").count() == 1
        assert db.query(RegistryCompany).filter(
            RegistryCompany.cnpj == "33000167000101").count() == 0
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_empresas_file_enriches_base_fields(tmp_path):
    from database.models import RegistryCompany
    from services.registry.importer import RegistryFileSpec, RegistryImporter

    engine, db = _db()
    try:
        fest = tmp_path / "ESTABELE0"
        fest.write_text(_estab("33000167", "0001", "01"), encoding="latin-1")
        femp = tmp_path / "EMPRESA0"
        femp.write_text(
            '"33000167";"PETROLEO BRASILEIRO S A PETROBRAS";"2011";"10";"100000000,00";"05";""',
            encoding="latin-1",
        )
        snap = RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month="2026-08",
            files=[
                RegistryFileSpec(table_kind="estabelecimentos", path=str(fest), file_name="ESTABELE0"),
                RegistryFileSpec(table_kind="empresas", path=str(femp), file_name="EMPRESA0"),
            ],
        )
        assert snap.status == "COMPLETED"
        db.expire_all()
        row = db.query(RegistryCompany).filter(
            RegistryCompany.cnpj == "33000167000101").one()
        assert row.razao_social == "PETROLEO BRASILEIRO S A PETROBRAS"
        assert row.porte == "05"
        assert row.natureza_juridica == "2011"
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_secundarios_e_referencia_sao_importados(tmp_path):
    from database.models import RegistryCnae, RegistryCompanyCnae
    from services.registry.importer import RegistryFileSpec, RegistryImporter
    from services.registry.search import RegistrySearchService, SearchFilters

    engine, db = _db()
    try:
        cols = _estab("33000167", "0001", "01").split(";")
        cols[12] = '"1922501,1931400"'
        fest = tmp_path / "ESTABELE0"
        fest.write_text(";".join(cols), encoding="latin-1")
        fcnae = tmp_path / "CNAE"
        fcnae.write_text('"6000001";"Extração de petróleo"\n"1922501";"Fabricação"', encoding="latin-1")
        snap = RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month="2026-08",
            files=[
                RegistryFileSpec(table_kind="estabelecimentos", path=str(fest), file_name="ESTABELE0"),
                RegistryFileSpec(table_kind="cnaes", path=str(fcnae), file_name="CNAE"),
            ],
        )
        assert snap.status == "COMPLETED"
        assert db.query(RegistryCompanyCnae).filter(
            RegistryCompanyCnae.cnpj == "33000167000101").count() == 2
        assert db.query(RegistryCnae).count() >= 2
        found = RegistrySearchService(db).search(SearchFilters(cnaes=["1931400"]))
        assert [c.cnpj for c in found.items] == ["33000167000101"]
        assert found.items[0].cnae_principal_label == "Extração de petróleo"
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_concurrent_imports_same_cnpj_stay_consistent(tmp_path):
    """Dois importadores concorrentes no mesmo snapshot: sem duplicata, sem erro."""
    from concurrent.futures import ThreadPoolExecutor

    from services.registry.importer import RegistryFileSpec, RegistryImporter

    engine, db = _db()
    db.close()
    try:
        fa = tmp_path / "EA"
        fb = tmp_path / "EB"
        fa.write_text(_estab("33000167", "0001", "01", fantasia="VIA A"), encoding="latin-1")
        fb.write_text(_estab("33000167", "0001", "01", fantasia="VIA B"), encoding="latin-1")

        def run(name, path):
            from sqlalchemy.orm import sessionmaker

            session = sessionmaker(bind=engine, expire_on_commit=False)()
            try:
                return RegistryImporter(session, batch_size=10).import_snapshot(
                    snapshot_month="2026-08",
                    files=[RegistryFileSpec(table_kind="estabelecimentos", path=str(path), file_name=name)],
                ).status
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda args: run(*args), [("EA", fa), ("EB", fb)]))
        assert statuses == ["COMPLETED", "COMPLETED"]
        check = sessionmaker(bind=engine, expire_on_commit=False)()
        try:
            from database.models import RegistryCompany

            rows = check.query(RegistryCompany).filter(
                RegistryCompany.cnpj == "33000167000101").all()
            assert len(rows) == 1
        finally:
            check.close()
    finally:
        cleaner = sessionmaker(bind=engine, expire_on_commit=False)()
        _cleanup(cleaner)
        cleaner.close()
        engine.dispose()


def _cleanup(db):
    from database.models import (
        RegistryCnae,
        RegistryCompany,
        RegistryCompanyCnae,
        RegistryImportFile,
        RegistrySnapshot,
    )

    db.query(RegistryCompanyCnae).delete(synchronize_session=False)
    db.query(RegistryCompany).delete(synchronize_session=False)
    db.query(RegistryCnae).delete(synchronize_session=False)
    db.query(RegistryImportFile).delete(synchronize_session=False)
    db.query(RegistrySnapshot).filter(RegistrySnapshot.snapshot_month == "2026-08").delete(
        synchronize_session=False)
    db.commit()
