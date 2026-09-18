"""Escopo de importação + segurança de ativação (PR D).

Seams: `services.registry.scope` (puro, sem DB) e `RegistryImporter` /
`RegistrySearchService` (PG-gated, padrão de test_registry_ingestion).
CNPJs aqui são literais de fixture (DV válido quando passam pelo parser).
"""
from __future__ import annotations

import os

import pytest

E2E_DATABASE_URL = os.environ.get("E2E_DATABASE_URL")
needs_pg = pytest.mark.skipif(not E2E_DATABASE_URL, reason="E2E_DATABASE_URL não definido")

ESTAB = (
    '"33000167";"0001";"01";"1";"PETROBRAS";"2";"20200115";"00";"";"105";'
    '"20100110";"6000001";"6000002";"RUA";"A";"10";"";"B";"20031170";"RJ";"6001";'
    '"21";"1";"";"";"";"";"";"";""'
)
EMPRESA = '"33000167";"PETROBRAS S.A.";"2038";"49";"1000000,00";"05";""'


def test_scope_vazio_e_none():
    from services.registry.scope import parse_scope

    assert parse_scope() is None
    assert parse_scope(ufs=[], municipio_cods=[], cnaes=[], situacoes=[]) is None


def test_scope_rejeita_uf_e_cnae_invalidos():
    from services.registry.scope import parse_scope

    with pytest.raises(ValueError):
        parse_scope(ufs=["XX"])
    with pytest.raises(ValueError):
        parse_scope(cnaes=["invalido"])


def test_scope_combina_uf_municipio_cnae_exato():
    from services.registry.scope import parse_scope, scope_matches

    scope = parse_scope(ufs=["RJ"], municipio_cods=["6001"], cnaes=["6000001"])
    assert scope is not None
    record = {"uf": "RJ", "municipio_cod": "6001", "cnae_principal": "6000001",
              "cnaes_secundarios": [], "situacao": "2", "matriz": True}
    assert scope_matches(scope, record) is True
    assert scope_matches(scope, {**record, "uf": "SP"}) is False
    assert scope_matches(scope, {**record, "municipio_cod": "9999"}) is False
    assert scope_matches(scope, {**record, "cnae_principal": "7000001"}) is False


def test_scope_casa_secundario_e_prefixo():
    from services.registry.scope import parse_scope, scope_matches

    base = {"uf": "RJ", "municipio_cod": "6001", "cnae_principal": "7000001",
            "cnaes_secundarios": ["6000002"], "situacao": "2", "matriz": True}
    assert scope_matches(parse_scope(cnaes=["6000002"]), base) is True
    assert scope_matches(parse_scope(cnaes=["60"]), base) is True
    assert scope_matches(parse_scope(cnaes=["61"]), base) is False


def test_scope_casa_situacao_e_matriz():
    from services.registry.scope import parse_scope, scope_matches

    base = {"uf": "RJ", "municipio_cod": "6001", "cnae_principal": "6000001",
            "cnaes_secundarios": [], "situacao": "2", "matriz": True}
    assert scope_matches(parse_scope(situacoes=["02", "2"]), base) is True
    assert scope_matches(parse_scope(situacoes=["08"]), base) is False
    assert scope_matches(parse_scope(matriz=True), base) is True
    assert scope_matches(parse_scope(matriz=False), base) is False


def _db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)()


def _cleanup(db, months=()):
    from database.models import RegistryCompany, RegistrySnapshot

    db.query(RegistryCompany).filter(
        RegistryCompany.cnpj.in_(["33000167000101", "33592510000154"])).delete(
        synchronize_session=False)
    for month in months:
        snap = db.query(RegistrySnapshot).filter_by(
            source="receita_cnpj", snapshot_month=month).first()
        if snap is not None:
            db.delete(snap)
    db.commit()


@needs_pg
def test_import_filtrado_materializa_apenas_escopo(tmp_path):
    from services.registry.importer import RegistryFileSpec, RegistryImporter
    from services.registry.scope import parse_scope

    engine, db = _db()
    try:
        f = tmp_path / "ESTABELE0"
        f.write_text("\n".join([
            ESTAB,
            ESTAB.replace('"33000167";"0001";"01"', '"33592510";"0001";"54"').replace(
                '"6001"', '"7001"'),
        ]), encoding="latin-1")
        scope = parse_scope(municipio_cods=["6001"])
        snap = RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month="2026-08",
            files=[RegistryFileSpec(
                table_kind="estabelecimentos", path=str(f), file_name="ESTABELE0")],
            scope=scope,
        )
        assert snap.status == "COMPLETED"
        assert snap.processed == 2
        assert snap.inserted == 1
    finally:
        _cleanup(db, months=("2026-08",))
        db.close()
        engine.dispose()


@needs_pg
def test_busca_exclui_snapshot_com_falha(tmp_path):
    from database.models import (
        RegistryCompany,
        RegistrySnapshot,
        RegistrySnapshotMember,
    )
    from services.registry.search import RegistrySearchService, SearchFilters

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
        items = RegistrySearchService(db).search(SearchFilters(limit=100)).items
        assert {item.cnpj for item in items} == {"33000167000101"}
    finally:
        _cleanup(db, months=("2026-08", "2026-09"))
        db.close()
        engine.dispose()


@needs_pg
def test_busca_com_mes_explicito_ignora_ativo(tmp_path):
    from database.models import (
        RegistryCompany,
        RegistrySnapshot,
        RegistrySnapshotMember,
    )
    from services.registry.search import RegistrySearchService, SearchFilters

    engine, db = _db()
    try:
        snap_a = RegistrySnapshot(source="receita_cnpj", snapshot_month="2026-08",
                                  status="COMPLETED", is_active=True)
        snap_old = RegistrySnapshot(source="receita_cnpj", snapshot_month="2026-07",
                                    status="COMPLETED")
        db.add_all([snap_a, snap_old])
        db.flush()
        db.add(RegistryCompany(cnpj="33000167000101", cnpj_basico="33000167",
                               source="receita_cnpj", source_snapshot="2026-08"))
        db.add(RegistryCompany(cnpj="33592510000154", cnpj_basico="33592510",
                               source="receita_cnpj", source_snapshot="2026-07"))
        db.add(RegistrySnapshotMember(snapshot_id=snap_a.id,
                                      cnpj="33000167000101"))
        db.add(RegistrySnapshotMember(snapshot_id=snap_old.id,
                                      cnpj="33592510000154"))
        db.commit()
        items = RegistrySearchService(db).search(
            SearchFilters(limit=100, source_snapshot="2026-07")).items
        assert {item.cnpj for item in items} == {"33592510000154"}
    finally:
        _cleanup(db, months=("2026-08", "2026-07"))
        db.close()
        engine.dispose()


@needs_pg
def test_merge_empresas_atualiza_source_snapshot(tmp_path):
    from database.models import RegistryCompany
    from services.registry.activation import activate_snapshot
    from services.registry.importer import RegistryFileSpec, RegistryImporter

    engine, db = _db()
    try:
        festab = tmp_path / "ESTABELE0"
        festab.write_text(ESTAB, encoding="latin-1")
        RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month="2026-08",
            files=[RegistryFileSpec(
                table_kind="estabelecimentos", path=str(festab), file_name="ESTABELE0")],
        )
        activate_snapshot(db, source="receita_cnpj", snapshot_month="2026-08")
        femp = tmp_path / "EMPRESA0"
        femp.write_text(EMPRESA, encoding="latin-1")
        RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month="2026-09",
            files=[
                RegistryFileSpec(
                    table_kind="estabelecimentos", path=str(festab),
                    file_name="ESTABELE0"),
                RegistryFileSpec(
                    table_kind="empresas", path=str(femp), file_name="EMPRESA0"),
            ],
        )
        activate_snapshot(db, source="receita_cnpj", snapshot_month="2026-09")
        row = db.query(RegistryCompany).filter_by(cnpj="33000167000101").one()
        assert row.source_snapshot == "2026-09"
        assert row.razao_social == "PETROBRAS S.A."
    finally:
        _cleanup(db, months=("2026-08", "2026-09"))
        db.close()
        engine.dispose()
