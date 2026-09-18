"""Ativação sem write amplification (PR B1).

Seams: `activate_snapshot` + `RegistrySearchService` (PG real) e o contrato
de membership. `xmin` prova reescrita física: linha inalterada A→B mantém
`xmin` no canônico e nas associações; alterada avança. Membership de B é
completo nos dois casos; provenance de inalterada não é reescrita.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

E2E_DATABASE_URL = os.environ.get("E2E_DATABASE_URL")
needs_pg = pytest.mark.skipif(not E2E_DATABASE_URL, reason="E2E_DATABASE_URL não definido")

SOURCE = "receita_cnpj"
MONTH_A = "2026-08"
MONTH_B = "2026-09"


def _dv_for(base12: str) -> str:
    from services.registry.cnpj import is_valid_cnpj

    for dv in range(100):
        candidate = f"{base12}{dv:02d}"
        if is_valid_cnpj(candidate):
            return candidate
    raise AssertionError(f"sem DV válido para {base12}")


def _cnpjs(n: int, *, start: int = 1) -> list[str]:
    out = []
    for index in range(start, start + n):
        out.append(_dv_for(f"{index:08d}0001"))
    assert len(set(out)) == n
    return out


def _estab_row(cnpj14: str, *, fantasia: str, secundarias: str = "") -> str:
    basico, ordem, dv = cnpj14[:8], cnpj14[8:12], cnpj14[12:]
    cols = [basico, ordem, dv, "1", fantasia, "02",
            "20200115", "00", "", "105", "20100110", "6000001", secundarias,
            "RUA", "A", "10", "", "B", "20031170", "RJ", "6001",
            "21", "1", "", "", "", "", "", "", ""]
    assert len(cols) == 30
    return ";".join(f'"{c}"' for c in cols)


def _db():
    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)()


def _import(db, tmp_path, month: str, rows: list[str], *, tag: str) -> None:
    from services.registry.importer import RegistryFileSpec, RegistryImporter

    path = tmp_path / f"ESTABELE_{tag}"
    path.write_text("\n".join(rows), encoding="latin-1")
    snap = RegistryImporter(db, batch_size=25).import_snapshot(
        snapshot_month=month,
        files=[RegistryFileSpec(table_kind="estabelecimentos", path=str(path),
                                file_name=f"ESTABELE_{tag}")],
    )
    assert snap.status == "COMPLETED"


def _activate(db, month: str) -> None:
    from services.registry.activation import activate_snapshot

    activate_snapshot(db, source=SOURCE, snapshot_month=month)


def _xmins(db) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    companies = dict(db.execute(text(
        "SELECT cnpj, xmin::text FROM registry_companies")).all())
    assoc = {(cnpj, cnae): xmin for cnpj, cnae, xmin in db.execute(text(
        "SELECT cnpj, cnae, xmin::text FROM registry_company_cnaes")).all()}
    return companies, assoc


def _search_set(db, **kwargs) -> set[str]:
    from services.registry.search import RegistrySearchService, SearchFilters

    found: set[str] = set()
    cursor = None
    while True:
        result = RegistrySearchService(db).search(
            SearchFilters(limit=100, cursor=cursor, **kwargs))
        found.update(item.cnpj for item in result.items)
        if not result.has_more:
            return found
        cursor = result.next_cursor


def _cleanup(db, cnpjs: list[str]) -> None:
    from database.models import RegistryCompany, RegistryCompanyCnae, RegistrySnapshot

    if cnpjs:
        db.query(RegistryCompanyCnae).filter(
            RegistryCompanyCnae.cnpj.in_(cnpjs)).delete(synchronize_session=False)
        db.query(RegistryCompany).filter(
            RegistryCompany.cnpj.in_(cnpjs)).delete(synchronize_session=False)
    for month in (MONTH_A, MONTH_B):
        snap = db.query(RegistrySnapshot).filter_by(
            source=SOURCE, snapshot_month=month).first()
        if snap is not None:
            db.delete(snap)
    db.commit()


@needs_pg
def test_activate_reaproveita_inalteradas_sem_rewrite(tmp_path):
    """100 em A; B com 90 idênticas + 10 alteradas: só 10 reescrevem."""
    from database.models import RegistryCompany, RegistryCompanyCnae

    engine, db = _db()
    cnpjs = _cnpjs(100)
    try:
        rows_a = [_estab_row(c, fantasia=f"EMP {i}",
                             secundarias="1922501,1931400" if i % 2 == 0 else "1922501")
                  for i, c in enumerate(cnpjs)]
        _import(db, tmp_path, MONTH_A, rows_a, tag="wa_a")
        _activate(db, MONTH_A)
        before_comp, before_assoc = _xmins(db)

        rows_b = [
            _estab_row(c, fantasia=(f"MUDADA {i}" if i >= 90 else f"EMP {i}"),
                       secundarias=("1931500" if i >= 95 else
                                    ("1922501,1931400" if i % 2 == 0 else "1922501")))
            for i, c in enumerate(cnpjs)
        ]
        _import(db, tmp_path, MONTH_B, rows_b, tag="wa_b")
        _activate(db, MONTH_B)

        from database.models import RegistrySnapshot, RegistrySnapshotMember

        snap_b_id = db.query(RegistrySnapshot.id).filter_by(
            source=SOURCE, snapshot_month=MONTH_B).scalar()
        members_b = {cnpj for (cnpj,) in db.query(RegistrySnapshotMember.cnpj).filter(
            RegistrySnapshotMember.snapshot_id == snap_b_id).all()}
        assert members_b == set(cnpjs)

        after_comp, after_assoc = _xmins(db)
        for i, cnpj in enumerate(cnpjs):
            if i < 90:
                assert after_comp[cnpj] == before_comp[cnpj], f"rewrite indevido: {cnpj}"
            else:
                assert after_comp[cnpj] != before_comp[cnpj], f"alterada não reescreveu: {cnpj}"
        for (cnpj, cnae), xmin in before_assoc.items():
            if cnpjs.index(cnpj) < 90:
                assert after_assoc[(cnpj, cnae)] == xmin, f"assoc reescrita: {cnpj}/{cnae}"

        changed = {c: r for c, r in
                   ((row.cnpj, row) for row in db.query(RegistryCompany).all())}
        for i, cnpj in enumerate(cnpjs):
            row = changed[cnpj]
            if i < 90:
                assert row.nome_fantasia == f"EMP {i}"
                assert row.source_snapshot == MONTH_A
            else:
                assert row.nome_fantasia == f"MUDADA {i}"
                assert row.source_snapshot == MONTH_B
        sec = {}
        for row in db.query(RegistryCompanyCnae).all():
            sec.setdefault(row.cnpj, set()).add(row.cnae)
        for i, cnpj in enumerate(cnpjs):
            if i < 90:
                expected = {"1922501", "1931400"} if i % 2 == 0 else {"1922501"}
            elif i < 95:
                expected = {"1922501", "1931400"} if i % 2 == 0 else {"1922501"}
            else:
                expected = {"1931500"}
            assert sec.get(cnpj, set()) == expected, cnpj

        assert _search_set(db) == set(cnpjs)
        assert _search_set(db, source_snapshot=MONTH_A) == set(cnpjs)
    finally:
        _cleanup(db, cnpjs)
        db.close()
        engine.dispose()
