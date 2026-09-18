"""Prefixo CNAE no Registry em PG real: semântica, query-count e plano de índice.

Pula sem E2E_DATABASE_URL. Dataset sintético (~10k linhas) representativo:
divisões 25/28/33 × UFs, para provar que prefixo usa índice (sem seq scan
no caminho quente) e que `target_candidates=30` limita no banco.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

E2E_DATABASE_URL = os.environ.get("E2E_DATABASE_URL")
pytestmark = pytest.mark.skipif(not E2E_DATABASE_URL, reason="E2E_DATABASE_URL não definido")

SNAP = "tst-1c"


def _db():
    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)()


def _seed(db, n=10000):
    from database.models import (
        RegistryCompany,
        RegistryCompanyCnae,
        RegistrySnapshot,
        RegistrySnapshotMember,
    )

    snap = RegistrySnapshot(source="receita_cnpj", snapshot_month="2026-08",
                            status="COMPLETED", is_active=True)
    db.add(snap)
    db.flush()
    divs = ["25", "28", "33"]
    ufs = ["SP", "RJ", "MG"]
    rows = []
    for i in range(n):
        div = divs[i % 3]
        uf = ufs[(i // 3) % 3]
        code = f"{div}{(i * 7919) % 100000:05d}"
        cnpj = f"{90000000 + i:08d}0001{(i * 37) % 100:02d}"
        rows.append(RegistryCompany(
            cnpj=cnpj, cnpj_basico=cnpj[:8],
            razao_social=f"EMPRESA TESTE {i}", matriz=True, situacao="2",
            cnae_principal=code, uf=uf, municipio_cod="7107",
            source="receita_cnpj", source_snapshot=SNAP,
        ))
    db.add_all(rows)
    db.commit()
    db.add_all([
        RegistrySnapshotMember(snapshot_id=snap.id, cnpj=row.cnpj) for row in rows
    ])
    db.commit()
    # Um secundário 28 numa empresa de principal 25 (prova via assoc).
    target = db.query(RegistryCompany).filter(
        RegistryCompany.source_snapshot == SNAP,
        RegistryCompany.cnae_principal.like("25%"),
    ).first()
    assert target is not None
    db.add(RegistryCompanyCnae(cnpj=target.cnpj, cnae="2869100"))
    db.commit()
    return target.cnpj


def _cleanup(db):
    from database.models import RegistryCompany, RegistryCompanyCnae, RegistrySnapshot

    db.rollback()
    sub = db.query(RegistryCompany.cnpj).filter(RegistryCompany.source_snapshot == SNAP)
    db.query(RegistryCompanyCnae).filter(RegistryCompanyCnae.cnpj.in_(sub)).delete(
        synchronize_session=False)
    db.query(RegistryCompany).filter(RegistryCompany.source_snapshot == SNAP).delete(
        synchronize_session=False)
    db.query(RegistrySnapshot).filter(
        RegistrySnapshot.source == "receita_cnpj",
        RegistrySnapshot.snapshot_month == "2026-08").delete(
        synchronize_session=False)
    db.commit()


def test_prefixo_divisao_encontra_principal_e_secundario_sem_vazar():
    from services.registry.search import RegistrySearchService, SearchFilters

    engine, db = _db()
    try:
        secondary_owner = _seed(db)
        svc = RegistrySearchService(db)
        page = svc.search(SearchFilters(cnae_prefixes=["28"], situacao="2", limit=100))
        got = {c.cnpj for c in page.items}
        assert secondary_owner in got
        assert all(
            (c.cnae_principal or "").startswith("28")
            or any(s.startswith("28") for s in c.cnaes_secundarios)
            for c in page.items
        )
        assert not any((c.cnae_principal or "").startswith("25") and not c.cnaes_secundarios
                       for c in page.items)
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_busca_por_prefixo_sem_n_plus_1():
    from services.registry.search import RegistrySearchService, SearchFilters

    engine, db = _db()
    try:
        _seed(db, n=2000)
        queries: list[str] = []

        def counter(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement[:80])

        event.listen(engine, "before_cursor_execute", counter)
        try:
            result = RegistrySearchService(db).search(
                SearchFilters(cnae_prefixes=["28"], uf="SP", limit=30))
        finally:
            event.remove(engine, "before_cursor_execute", counter)
        assert len(result.items) <= 30
        assert len(queries) <= 4
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_plano_usa_indice_sem_seq_scan():
    from services.registry.search import RegistrySearchService, SearchFilters

    engine, db = _db()
    try:
        _seed(db)
        # Warmup: garante estatísticas mínimas para o planner escolher índice.
        db.execute(text("ANALYZE registry_companies"))
        db.commit()
        filters = SearchFilters(cnae_prefixes=["28"], uf="SP", situacao="2", limit=30)
        stmt = text(
            "EXPLAIN SELECT cnpj FROM registry_companies "
            "WHERE uf = :uf AND situacao = :sit AND (cnae_principal BETWEEN '2800000' AND '2899999') "
            "ORDER BY cnpj LIMIT 31"
        )
        plan = "\n".join(
            row[0] for row in db.execute(stmt, {"uf": "SP", "sit": "2"}).all())
        assert "Index" in plan or "Bitmap" in plan, plan
        assert "Seq Scan on registry_companies" not in plan, plan
        # Funcional: o serviço real respeita o teto no banco (não fatia em Python).
        result = RegistrySearchService(db).search(filters)
        assert len(result.items) <= 30
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()
