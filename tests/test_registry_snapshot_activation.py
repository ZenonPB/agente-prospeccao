"""Ativação atômica de snapshot do Registry (PR1: P1A + P1B).

Seams: `services.registry.activation` (activate/get_active) +
`RegistryImporter` (staging invisível) + `RegistrySearchService` (visibilidade
por membership). PG-gated, padrão de test_registry_ingestion.

Contrato:
- import NÃO publica: search() enxerga o snapshot ACTIVE;
- membership é por observação (inalteradas continuam visíveis após activate);
- falha de B nunca altera o universo observável de A (conjunto E conteúdo);
- COMPLETED != ACTIVE; ativação é uma transação (rollback preserva A);
- histórico COMPLETED com membership continua reproduzível por mês explícito;
- mês explícito desconhecido/não utilizável falha fechado.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

E2E_DATABASE_URL = os.environ.get("E2E_DATABASE_URL")
needs_pg = pytest.mark.skipif(not E2E_DATABASE_URL, reason="E2E_DATABASE_URL não definido")

SOURCE = "receita_cnpj"
MONTH_A = "2026-08"
MONTH_B = "2026-09"


def test_contrato_de_ativacao_existe():
    """Tracer sem DB: o módulo e as funções do contrato precisam existir."""
    from services.registry import activation

    assert callable(activation.activate_snapshot)
    assert callable(activation.get_active_snapshot)
    assert issubclass(activation.SnapshotActivationError, Exception)


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
        base12 = f"{index:08d}0001"
        full = _dv_for(base12)
        out.append(full)
    assert len(set(out)) == n
    return out


def _estab_row(cnpj14: str, *, fantasia: str = "EMPRESA", situacao: str = "2",
               cnae: str = "6000001", uf: str = "RJ", mun: str = "6001") -> str:
    basico, ordem, dv = cnpj14[:8], cnpj14[8:12], cnpj14[12:]
    cols = [basico, ordem, dv, "1" if ordem == "0001" else "2", fantasia, situacao,
            "20200115", "00", "", "105", "20100110", cnae, "", "RUA", "A",
            "10", "", "B", "20031170", uf, mun,
            "21", "1", "", "", "", "", "", "", ""]
    assert len(cols) == 30
    return ";".join(f'"{c}"' for c in cols)


def _db():
    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)()


def _import_month(db, tmp_path, month: str, rows: list[str], *, tag: str) -> None:
    from services.registry.importer import RegistryFileSpec, RegistryImporter

    path = tmp_path / f"ESTABELE_{tag}_{month.replace('-', '')}"
    path.write_text("\n".join(rows), encoding="latin-1")
    snap = RegistryImporter(db, batch_size=10).import_snapshot(
        snapshot_month=month,
        files=[RegistryFileSpec(
            table_kind="estabelecimentos", path=str(path),
            file_name=f"ESTABELE_{tag}")],
    )
    assert snap.status == "COMPLETED"


def _activate(db, month: str):
    from services.registry.activation import activate_snapshot

    return activate_snapshot(db, source=SOURCE, snapshot_month=month)


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


def _search_rows(db, **kwargs) -> dict[str, object]:
    from services.registry.search import RegistrySearchService, SearchFilters

    rows: dict[str, object] = {}
    cursor = None
    while True:
        result = RegistrySearchService(db).search(
            SearchFilters(limit=100, cursor=cursor, **kwargs))
        for item in result.items:
            rows[item.cnpj] = (item.nome_fantasia, item.cnae_principal,
                               item.uf, item.situacao, item.source_snapshot)
        if not result.has_more:
            return rows
        cursor = result.next_cursor


def _cleanup(db, cnpjs: list[str], months: tuple[str, ...] = (MONTH_A, MONTH_B)):
    from database.models import (
        RegistryCompany,
        RegistryCompanyCnae,
        RegistrySnapshot,
    )

    try:
        from database.models import RegistrySnapshotMember  # type: ignore
    except ImportError:
        RegistrySnapshotMember = None  # type: ignore
    try:
        from database.models import RegistryStagingCompany  # type: ignore
    except ImportError:
        RegistryStagingCompany = None  # type: ignore
    try:
        from database.models import RegistryStagingCompanyCnae  # type: ignore
    except ImportError:
        RegistryStagingCompanyCnae = None  # type: ignore
    if RegistryStagingCompanyCnae is not None:
        db.query(RegistryStagingCompanyCnae).delete(synchronize_session=False)
    if RegistryStagingCompany is not None:
        db.query(RegistryStagingCompany).delete(synchronize_session=False)
    db.query(RegistryCompanyCnae).filter(
        RegistryCompanyCnae.cnpj.in_(cnpjs)).delete(synchronize_session=False)
    if cnpjs:
        db.query(RegistryCompany).filter(
            RegistryCompany.cnpj.in_(cnpjs)).delete(synchronize_session=False)
    if RegistrySnapshotMember is not None:
        db.query(RegistrySnapshotMember).delete(synchronize_session=False)
    for month in months:
        snap = db.query(RegistrySnapshot).filter_by(
            source=SOURCE, snapshot_month=month).first()
        if snap is not None:
            db.delete(snap)
    db.commit()


@needs_pg
def test_import_sem_ativacao_nao_publica(tmp_path):
    """CASO 1: A ACTIVE + B COMPLETED não ativado → search() = A."""
    from services.registry.activation import get_active_snapshot

    engine, db = _db()
    cnpjs_a = _cnpjs(4)
    cnpjs_b = _cnpjs(4, start=500)
    try:
        _import_month(db, tmp_path, MONTH_A,
                      [_estab_row(c) for c in cnpjs_a], tag="a1")
        _activate(db, MONTH_A)
        _import_month(db, tmp_path, MONTH_B,
                      [_estab_row(c) for c in cnpjs_b], tag="b1")
        assert get_active_snapshot(db, source=SOURCE).snapshot_month == MONTH_A
        assert _search_set(db) == set(cnpjs_a)
    finally:
        _cleanup(db, cnpjs_a + cnpjs_b)
        db.close()
        engine.dispose()


@needs_pg
def test_completed_sem_ativacao_nao_assume(tmp_path):
    """CASO 3: B COMPLETED explícito ainda não ACTIVE → default segue A."""
    engine, db = _db()
    cnpjs_a = _cnpjs(3)
    cnpjs_b = _cnpjs(3, start=500)
    try:
        _import_month(db, tmp_path, MONTH_A,
                      [_estab_row(c) for c in cnpjs_a], tag="a3")
        _activate(db, MONTH_A)
        _import_month(db, tmp_path, MONTH_B,
                      [_estab_row(c) for c in cnpjs_b], tag="b3")
        assert _search_set(db) == set(cnpjs_a)
        assert _search_set(db, source_snapshot=MONTH_B) == set(cnpjs_b)
    finally:
        _cleanup(db, cnpjs_a + cnpjs_b)
        db.close()
        engine.dispose()


@needs_pg
def test_activate_troca_visibilidade(tmp_path):
    """CASO 4: activate(B) → search() = membership B."""
    engine, db = _db()
    cnpjs_a = _cnpjs(3)
    cnpjs_b = _cnpjs(4, start=500)
    try:
        _import_month(db, tmp_path, MONTH_A,
                      [_estab_row(c) for c in cnpjs_a], tag="a4")
        _activate(db, MONTH_A)
        _import_month(db, tmp_path, MONTH_B,
                      [_estab_row(c) for c in cnpjs_b], tag="b4")
        _activate(db, MONTH_B)
        assert _search_set(db) == set(cnpjs_b)
    finally:
        _cleanup(db, list(set(cnpjs_a + cnpjs_b)))
        db.close()
        engine.dispose()


@needs_pg
def test_inalteradas_continuam_visiveis_apos_activate(tmp_path):
    """CASO 5 (P1A): 100 em A; B com 90 idênticas + 10 mudadas → 100 visíveis."""
    engine, db = _db()
    cnpjs = _cnpjs(100)
    try:
        _import_month(db, tmp_path, MONTH_A,
                      [_estab_row(c, fantasia=f"EMP {i}")
                       for i, c in enumerate(cnpjs)], tag="a5")
        _activate(db, MONTH_A)
        rows_b = [
            _estab_row(c, fantasia=(f"MUDADA {i}" if i >= 90 else f"EMP {i}"))
            for i, c in enumerate(cnpjs)
        ]
        _import_month(db, tmp_path, MONTH_B, rows_b, tag="b5")
        _activate(db, MONTH_B)
        assert _search_set(db) == set(cnpjs)
    finally:
        _cleanup(db, cnpjs)
        db.close()
        engine.dispose()


@needs_pg
def test_falha_preserva_ativo_integralmente(tmp_path):
    """CASO 2/6 (P1B): B altera chunks e falha → universo de A intacto (set+conteúdo)."""
    from services.registry.importer import RegistryFileSpec, RegistryImporter

    engine, db = _db()
    cnpjs_a = _cnpjs(6)
    cnpjs_extra = _cnpjs(2, start=900)
    try:
        _import_month(db, tmp_path, MONTH_A,
                      [_estab_row(c, fantasia=f"A {c[-4:]}") for c in cnpjs_a],
                      tag="a6")
        _activate(db, MONTH_A)
        antes = _search_rows(db)
        assert set(antes) == set(cnpjs_a)
        bom = tmp_path / "ESTABELE_OK"
        bom.write_text("\n".join(
            [_estab_row(c, fantasia="B ALTERADA") for c in cnpjs_a]
            + [_estab_row(c, fantasia="B NOVA") for c in cnpjs_extra]
        ), encoding="latin-1")
        snap = RegistryImporter(db, batch_size=2).import_snapshot(
            snapshot_month=MONTH_B,
            files=[
                RegistryFileSpec(table_kind="estabelecimentos", path=str(bom),
                                 file_name="ESTABELE_OK"),
                RegistryFileSpec(table_kind="estabelecimentos",
                                 path=str(tmp_path / "AUSENTE"),
                                 file_name="AUSENTE"),
            ],
        )
        assert snap.status == "FAILED"
        depois = _search_rows(db)
        assert depois == antes
    finally:
        _cleanup(db, cnpjs_a + cnpjs_extra)
        db.close()
        engine.dispose()


@needs_pg
def test_falha_de_ativacao_preserva_ativo(tmp_path):
    """CASO 7: erro no meio do activate → rollback, A continua ACTIVE."""
    from services.registry.activation import (
        SnapshotActivationError,
        get_active_snapshot,
    )

    engine, db = _db()
    cnpjs_a = _cnpjs(3)
    cnpjs_b = _cnpjs(3, start=500)
    try:
        _import_month(db, tmp_path, MONTH_A,
                      [_estab_row(c) for c in cnpjs_a], tag="a7")
        _activate(db, MONTH_A)
        _import_month(db, tmp_path, MONTH_B,
                      [_estab_row(c) for c in cnpjs_b], tag="b7")
        import services.registry.activation as activation_mod

        real_apply = activation_mod._apply_activation

        def _quebrada(*args, **kwargs):
            raise RuntimeError("falha injetada no meio da ativação")

        activation_mod._apply_activation = _quebrada
        try:
            with pytest.raises((SnapshotActivationError, RuntimeError)):
                _activate(db, MONTH_B)
        finally:
            activation_mod._apply_activation = real_apply
        db.rollback()
        assert get_active_snapshot(db, source=SOURCE).snapshot_month == MONTH_A
        assert _search_set(db) == set(cnpjs_a)
    finally:
        _cleanup(db, cnpjs_a + cnpjs_b)
        db.close()
        engine.dispose()


@needs_pg
def test_historico_continua_reproduzivel(tmp_path):
    """CASO 8: B ACTIVE, mas search(month=A) reproduz A (retenção)."""
    engine, db = _db()
    cnpjs_a = _cnpjs(3)
    cnpjs_b = _cnpjs(4, start=500)
    try:
        _import_month(db, tmp_path, MONTH_A,
                      [_estab_row(c) for c in cnpjs_a], tag="a8")
        _activate(db, MONTH_A)
        _import_month(db, tmp_path, MONTH_B,
                      [_estab_row(c) for c in cnpjs_b], tag="b8")
        _activate(db, MONTH_B)
        assert _search_set(db) == set(cnpjs_b)
        assert _search_set(db, source_snapshot=MONTH_A) == set(cnpjs_a)
    finally:
        _cleanup(db, list(set(cnpjs_a + cnpjs_b)))
        db.close()
        engine.dispose()


@needs_pg
def test_ativacao_concorrente_mantem_um_ativo(tmp_path):
    """CASO 9: activates simultâneos → exatamente um ACTIVE; search consistente."""
    from concurrent.futures import ThreadPoolExecutor

    from services.registry.activation import get_active_snapshot

    engine, db = _db()
    cnpjs_a = _cnpjs(3)
    cnpjs_b = _cnpjs(3, start=500)
    try:
        _import_month(db, tmp_path, MONTH_A,
                      [_estab_row(c) for c in cnpjs_a], tag="a9")
        _import_month(db, tmp_path, MONTH_B,
                      [_estab_row(c) for c in cnpjs_b], tag="b9")

        def _run(month: str) -> str:
            from services.registry.activation import SnapshotActivationError

            session = sessionmaker(bind=engine, expire_on_commit=False)()
            try:
                try:
                    from services.registry.activation import activate_snapshot

                    activate_snapshot(session, source=SOURCE, snapshot_month=month)
                    return "ok"
                except SnapshotActivationError:
                    return "conflito"
            finally:
                session.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(_run, [MONTH_A, MONTH_B]))
        assert resultados.count("ok") >= 1
        db.expire_all()
        from database.models import RegistrySnapshot

        ativos = db.query(RegistrySnapshot).filter(
            RegistrySnapshot.source == SOURCE,
            RegistrySnapshot.is_active.is_(True)).all()
        assert len(ativos) == 1
        vencedor = get_active_snapshot(db, source=SOURCE).snapshot_month
        esperado = set(cnpjs_a) if vencedor == MONTH_A else set(cnpjs_b)
        assert _search_set(db) == esperado
    finally:
        _cleanup(db, cnpjs_a + cnpjs_b)
        db.close()
        engine.dispose()


@needs_pg
def test_migration_head_unico_e_schema_ativacao():
    """CASO 10: banco novo + upgrade head (2x idempotente) + contrato de schema."""
    from sqlalchemy import inspect

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    head = ScriptDirectory.from_config(
        Config("services/workers/alembic.ini")).get_heads()
    assert head == ["e5f6a7b8c9d0"]

    engine, db = _db()
    try:
        from alembic import command

        cfg = Config("services/workers/alembic.ini")
        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        assert {"registry_snapshot_members", "registry_staging_companies",
                "registry_staging_company_cnaes"} <= tables
        snap_cols = {c["name"] for c in insp.get_columns("registry_snapshots")}
        assert "is_active" in snap_cols
        indexes = {i["name"] for i in insp.get_indexes("registry_snapshots")}
        assert "uq_registry_snapshots_active_per_source" in indexes
    finally:
        db.close()
        engine.dispose()


@needs_pg
def test_backfill_reconstroi_ativo_do_estado_legado():
    """CASO 11: estado pré-migration (sem membership) → backfill real da migration."""
    import importlib.util

    from database.models import RegistryCompany, RegistrySnapshot

    engine, db = _db()
    cnpjs = _cnpjs(3)
    try:
        db.add(RegistrySnapshot(source=SOURCE, snapshot_month=MONTH_A,
                                status="COMPLETED", is_active=False))
        db.add(RegistrySnapshot(source=SOURCE, snapshot_month=MONTH_B,
                                status="FAILED", is_active=False))
        for cnpj in cnpjs:
            db.add(RegistryCompany(cnpj=cnpj, cnpj_basico=cnpj[:8],
                                   source=SOURCE, source_snapshot=MONTH_A))
        db.commit()
        spec = importlib.util.spec_from_file_location(
            "migration_activation",
            "services/workers/migrations/versions/"
            "e5f6a7b8c9d0_registry_snapshot_activation.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with engine.begin() as conn:
            module.backfill(conn)
        db.expire_all()
        from services.registry.activation import get_active_snapshot

        active = get_active_snapshot(db, source=SOURCE)
        assert active is not None and active.snapshot_month == MONTH_A
        assert _search_set(db) == set(cnpjs)
    finally:
        _cleanup(db, cnpjs)
        db.close()
        engine.dispose()


@needs_pg
def test_mes_explicito_invalido_falha_fechado(tmp_path):
    """Mês inexistente ou FAILED nunca cai em fallback silencioso."""
    engine, db = _db()
    cnpjs_a = _cnpjs(2)
    try:
        _import_month(db, tmp_path, MONTH_A,
                      [_estab_row(c) for c in cnpjs_a], tag="a10")
        _activate(db, MONTH_A)
        with pytest.raises(ValueError):
            _search_set(db, source_snapshot="2026-07")
    finally:
        _cleanup(db, cnpjs_a)
        db.close()
        engine.dispose()
