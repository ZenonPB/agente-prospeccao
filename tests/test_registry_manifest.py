"""Manifesto de snapshot oficial do Registry (PR B).

Seam: `services.registry.manifest` (puro, sem DB/rede) + integração no
`RegistryImporter` (PG-gated, mesmo padrão de test_registry_ingestion).
Nenhum teste depende de rede, snapshot real ou data atual: hashes e datas
são literais fixos ou arquivos temporários.
"""
from __future__ import annotations

import hashlib
import json
import os

import pytest

E2E_DATABASE_URL = os.environ.get("E2E_DATABASE_URL")
needs_pg = pytest.mark.skipif(not E2E_DATABASE_URL, reason="E2E_DATABASE_URL não definido")

ESTAB = (
    '"33000167";"0001";"01";"1";"PETROBRAS";"2";"20200115";"00";"";"105";'
    '"20100110";"6000001";"";"RUA";"A";"10";"";"B";"20031170";"RJ";"6001";'
    '"21";"1";"";"";"";"";"";"";""'
)


def _manifest_dict(**overrides):
    base = {
        "manifest_version": "1",
        "source": "receita_cnpj",
        "snapshot_month": "2026-08",
        "layout": "NOVOLAYOUTDOSDADOSABERTOSDOCNPJ",
        "layout_version": "2026-08",
        "encoding": "latin-1",
        "origin_kind": "receita_oficial",
        "origin_url": "https://arquivos.receitafederal.gov.br/dados/cnpj/2026-08",
        "accessed_at": "2026-09-01",
        "files": [
            {"table_kind": "estabelecimentos", "file_name": "ESTABELE0"},
        ],
    }
    base.update(overrides)
    return base


def test_parse_manifesto_minimo_valido():
    from services.registry.manifest import parse_manifest

    manifest = parse_manifest(_manifest_dict())
    assert manifest.snapshot_month == "2026-08"
    assert manifest.layout_version == "2026-08"
    assert len(manifest.files) == 1
    assert manifest.files[0].table_kind == "estabelecimentos"


def test_parse_rejeita_mes_invalido():
    from services.registry.manifest import ManifestError, parse_manifest

    with pytest.raises(ManifestError):
        parse_manifest(_manifest_dict(snapshot_month="08/2026"))


def test_parse_rejeita_origem_oficial_fora_da_allowlist():
    from services.registry.manifest import ManifestError, parse_manifest

    with pytest.raises(ManifestError):
        parse_manifest(_manifest_dict(origin_url="https://espelho.example.com/2026-08"))


def test_parse_aceita_espelho_explicito_com_https():
    from services.registry.manifest import parse_manifest

    manifest = parse_manifest(_manifest_dict(
        origin_kind="espelho_terceiros",
        origin_url="https://espelho.example.com/2026-08",
    ))
    assert manifest.origin_kind == "espelho_terceiros"


def test_parse_rejeita_url_sem_https():
    from services.registry.manifest import ManifestError, parse_manifest

    with pytest.raises(ManifestError):
        parse_manifest(_manifest_dict(
            origin_kind="espelho_terceiros",
            origin_url="http://espelho.example.com/2026-08",
        ))


def test_parse_exige_estabelecimentos():
    from services.registry.manifest import ManifestError, parse_manifest

    with pytest.raises(ManifestError):
        parse_manifest(_manifest_dict(files=[
            {"table_kind": "cnaes", "file_name": "CNAE"},
        ]))


def test_parse_rejeita_sha_invalido_e_bytes_negativo():
    from services.registry.manifest import ManifestError, parse_manifest

    with pytest.raises(ManifestError):
        parse_manifest(_manifest_dict(files=[
            {"table_kind": "estabelecimentos", "file_name": "ESTABELE0", "sha256": "xyz"},
        ]))
    with pytest.raises(ManifestError):
        parse_manifest(_manifest_dict(files=[
            {"table_kind": "estabelecimentos", "file_name": "ESTABELE0", "bytes": -1},
        ]))


def test_parse_rejeita_arquivo_duplicado_e_kind_desconhecido():
    from services.registry.manifest import ManifestError, parse_manifest

    with pytest.raises(ManifestError):
        parse_manifest(_manifest_dict(files=[
            {"table_kind": "estabelecimentos", "file_name": "ESTABELE0"},
            {"table_kind": "estabelecimentos", "file_name": "ESTABELE0"},
        ]))
    with pytest.raises(ManifestError):
        parse_manifest(_manifest_dict(files=[
            {"table_kind": "socios", "file_name": "SOCIOS0"},
        ]))


def test_load_e_dump_roundtrip(tmp_path):
    from services.registry.manifest import dump_manifest, load_manifest, parse_manifest

    manifest = parse_manifest(_manifest_dict())
    path = tmp_path / "manifest.json"
    path.write_text(dump_manifest(manifest), encoding="utf-8")
    assert load_manifest(str(path)) == manifest


def test_load_rejeita_json_invalido(tmp_path):
    from services.registry.manifest import ManifestError, load_manifest

    path = tmp_path / "manifest.json"
    path.write_text("{invalido", encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(str(path))


def _db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)()


def _cleanup(db):
    from database.models import RegistryCompany, RegistrySnapshot

    for cnpj in ("33000167000101",):
        row = db.query(RegistryCompany).filter_by(cnpj=cnpj).first()
        if row is not None:
            db.delete(row)
    snap = db.query(RegistrySnapshot).filter_by(source="receita_cnpj", snapshot_month="2026-08").first()
    if snap is not None:
        db.delete(snap)
    db.commit()


@needs_pg
def test_import_registra_layout_version_do_manifesto(tmp_path):
    from services.registry.importer import RegistryFileSpec, RegistryImporter
    from services.registry.manifest import parse_manifest

    engine, db = _db()
    try:
        f = tmp_path / "ESTABELE0"
        f.write_text(ESTAB, encoding="latin-1")
        manifest = parse_manifest(_manifest_dict())
        snap = RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month="2026-08",
            files=[RegistryFileSpec(
                table_kind="estabelecimentos", path=str(f), file_name="ESTABELE0")],
            manifest=manifest,
        )
        assert snap.status == "COMPLETED"
        assert snap.layout_version == "2026-08"
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


@needs_pg
def test_import_falha_fechado_com_tamanho_divergente(tmp_path):
    from services.registry.importer import RegistryFileSpec, RegistryImporter
    from services.registry.manifest import parse_manifest

    engine, db = _db()
    try:
        f = tmp_path / "ESTABELE0"
        f.write_text(ESTAB, encoding="latin-1")
        manifest = parse_manifest(_manifest_dict(files=[
            {"table_kind": "estabelecimentos", "file_name": "ESTABELE0", "bytes": 1},
        ]))
        snap = RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month="2026-08",
            files=[RegistryFileSpec(
                table_kind="estabelecimentos", path=str(f), file_name="ESTABELE0")],
            manifest=manifest,
        )
        assert snap.status == "FAILED"
        assert snap.failed == 1
        assert snap.inserted == 0
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


@needs_pg
def test_import_marca_falha_com_sha_divergente(tmp_path):
    from services.registry.importer import RegistryFileSpec, RegistryImporter
    from services.registry.manifest import parse_manifest

    engine, db = _db()
    try:
        f = tmp_path / "ESTABELE0"
        raw = ESTAB.encode("latin-1")
        f.write_bytes(raw)
        real = hashlib.sha256(raw).hexdigest()
        wrong = "0" * 63 + ("1" if real[-1] != "1" else "2")
        manifest = parse_manifest(_manifest_dict(files=[
            {"table_kind": "estabelecimentos", "file_name": "ESTABELE0",
             "bytes": len(raw), "sha256": wrong},
        ]))
        snap = RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month="2026-08",
            files=[RegistryFileSpec(
                table_kind="estabelecimentos", path=str(f), file_name="ESTABELE0")],
            manifest=manifest,
        )
        assert snap.status == "FAILED"
        assert snap.failed == 1
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


@needs_pg
def test_import_recusa_encoding_divergente(tmp_path):
    from services.registry.importer import RegistryFileSpec, RegistryImporter
    from services.registry.manifest import parse_manifest

    engine, db = _db()
    try:
        f = tmp_path / "ESTABELE0"
        f.write_text(ESTAB, encoding="latin-1")
        manifest = parse_manifest(_manifest_dict(encoding="utf-8"))
        with pytest.raises(ValueError):
            RegistryImporter(db, batch_size=10, encoding="latin-1").import_snapshot(
                snapshot_month="2026-08",
                files=[RegistryFileSpec(
                    table_kind="estabelecimentos", path=str(f), file_name="ESTABELE0")],
                manifest=manifest,
            )
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


@needs_pg
def test_import_recusa_manifesto_de_outro_mes(tmp_path):
    from services.registry.importer import RegistryFileSpec, RegistryImporter
    from services.registry.manifest import parse_manifest

    engine, db = _db()
    try:
        f = tmp_path / "ESTABELE0"
        f.write_text(ESTAB, encoding="latin-1")
        manifest = parse_manifest(_manifest_dict(snapshot_month="2026-07"))
        with pytest.raises(ValueError):
            RegistryImporter(db, batch_size=10).import_snapshot(
                snapshot_month="2026-08",
                files=[RegistryFileSpec(
                    table_kind="estabelecimentos", path=str(f), file_name="ESTABELE0")],
                manifest=manifest,
            )
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()
