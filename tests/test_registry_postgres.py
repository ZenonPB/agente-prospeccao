"""Registry em PostgreSQL real: constraints, unicidade, idempotência, globalidade.

Sem SQLite: comportamento PG (upsert por CNPJ, FK, tipos) só vale no PG.
Pula sem E2E_DATABASE_URL (igual aos demais gates PG do repo).
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

E2E_DATABASE_URL = os.environ.get("E2E_DATABASE_URL")
pytestmark = pytest.mark.skipif(not E2E_DATABASE_URL, reason="E2E_DATABASE_URL não definido")


def _session():
    from database.models import Base  # noqa: F401  (garante models registrados)

    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)()


def test_snapshot_e_arquivo_criam_ledger_global_sem_org():
    from database.models import RegistryImportFile, RegistrySnapshot

    engine, db = _session()
    try:
        snap = RegistrySnapshot(source="receita_cnpj", snapshot_month="2026-08")
        db.add(snap)
        db.flush()
        assert snap.id is not None
        assert not hasattr(snap, "organization_id")
        arq = RegistryImportFile(
            snapshot_id=snap.id, table_kind="estabelecimentos",
            file_name="ESTABELE0.zip", status="RUNNING",
        )
        db.add(arq)
        db.commit()
        assert arq.processed_lines == 0
    finally:
        db.close()
        engine.dispose()


def test_empresa_upsert_por_cnpj_e_idempotente():
    from sqlalchemy.dialects.postgresql import insert

    from database.models import RegistryCompany

    engine, db = _session()
    cnpj = "33000167000101"
    try:
        for fantasia in ("PETROBRAS", "PETROBRAS ATUALIZADA"):
            stmt = insert(RegistryCompany).values(
                cnpj=cnpj, cnpj_basico="33000167", nome_fantasia=fantasia,
                matriz=True, situacao="2", cnae_principal="6000001",
                uf="RJ", municipio_cod="6001",
                source="receita_cnpj", source_snapshot="2026-08",
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["cnpj"],
                set_={"nome_fantasia": stmt.excluded.nome_fantasia},
            )
            db.execute(stmt)
        db.commit()
        rows = db.query(RegistryCompany).filter(RegistryCompany.cnpj == cnpj).all()
        assert len(rows) == 1
        assert rows[0].nome_fantasia == "PETROBRAS ATUALIZADA"
    finally:
        db.query(RegistryCompany).filter(RegistryCompany.cnpj == cnpj).delete(
            synchronize_session=False)
        db.commit()
        db.close()
        engine.dispose()


def test_cnae_secundario_tem_fk_e_pk_composta():
    from database.models import RegistryCompany, RegistryCompanyCnae

    engine, db = _session()
    cnpj = "33592510000154"
    try:
        db.add(RegistryCompany(cnpj=cnpj, cnpj_basico="33592510", situacao="2"))
        db.flush()
        db.add(RegistryCompanyCnae(cnpj=cnpj, cnae="710301"))
        db.add(RegistryCompanyCnae(cnpj=cnpj, cnae="910001"))
        db.commit()
        assert db.query(RegistryCompanyCnae).filter(
            RegistryCompanyCnae.cnpj == cnpj).count() == 2
    finally:
        db.query(RegistryCompanyCnae).filter(
            RegistryCompanyCnae.cnpj == cnpj).delete(synchronize_session=False)
        db.query(RegistryCompany).filter(
            RegistryCompany.cnpj == cnpj).delete(synchronize_session=False)
        db.commit()
        db.close()
        engine.dispose()


def test_referencia_cnae():
    from database.models import RegistryCnae

    engine, db = _session()
    try:
        db.add(RegistryCnae(codigo="6000001", descricao="Extração de petróleo"))
        db.commit()
        assert db.query(RegistryCnae).filter(
            RegistryCnae.codigo == "6000001").count() == 1
    finally:
        db.query(RegistryCnae).filter(RegistryCnae.codigo == "6000001").delete(
            synchronize_session=False)
        db.commit()
        db.close()
        engine.dispose()
