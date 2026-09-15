"""Busca do Registry em PG real: filtros, keyset, candidato, sem N+1.

Pula sem E2E_DATABASE_URL.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

E2E_DATABASE_URL = os.environ.get("E2E_DATABASE_URL")
pytestmark = pytest.mark.skipif(not E2E_DATABASE_URL, reason="E2E_DATABASE_URL não definido")


def _db():
    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)()


def _seed(db):
    from database.models import RegistryCnae, RegistryCompany, RegistryCompanyCnae

    db.add_all([
        RegistryCompany(cnpj="33000167000101", cnpj_basico="33000167",
                        razao_social="PETROLEO BRASILEIRO S A PETROBRAS",
                        nome_fantasia="PETROBRAS", matriz=True, situacao="2",
                        cnae_principal="6000001", uf="RJ", municipio_cod="6001",
                        porte="05", source="receita_cnpj", source_snapshot="2026-08"),
        RegistryCompany(cnpj="33592510000154", cnpj_basico="33592510",
                        razao_social="VALE S.A.", nome_fantasia="VALE",
                        matriz=True, situacao="2", cnae_principal="710301",
                        uf="RJ", municipio_cod="6001", porte="05",
                        source="receita_cnpj", source_snapshot="2026-08"),
        RegistryCompany(cnpj="60701190000104", cnpj_basico="60701190",
                        razao_social="ITAU UNIBANCO S.A.", matriz=True,
                        situacao="08", cnae_principal="6421200", uf="SP",
                        municipio_cod="7107", source="receita_cnpj",
                        source_snapshot="2026-08"),
        RegistryCnae(codigo="6000001", descricao="Extração de petróleo"),
    ])
    db.add(RegistryCompanyCnae(cnpj="33000167000101", cnae="1922501"))
    db.commit()


def _cleanup(db):
    from database.models import RegistryCnae, RegistryCompany, RegistryCompanyCnae

    db.query(RegistryCompanyCnae).delete(synchronize_session=False)
    db.query(RegistryCompany).filter(
        RegistryCompany.cnpj.in_(["33000167000101", "33592510000154", "60701190000104"])).delete(
        synchronize_session=False)
    db.query(RegistryCnae).filter(RegistryCnae.codigo == "6000001").delete(
        synchronize_session=False)
    db.commit()


def test_lookup_cnpj_exato():
    from services.registry.search import RegistrySearchService, SearchFilters

    engine, db = _db()
    try:
        _seed(db)
        result = RegistrySearchService(db).search(SearchFilters(cnpj="33.000.167/0001-01"))
        assert len(result.items) == 1
        cand = result.items[0]
        assert cand.cnpj == "33000167000101"
        assert cand.razao_social == "PETROLEO BRASILEIRO S A PETROBRAS"
        assert cand.cnae_principal == "6000001"
        assert cand.cnae_principal_label == "Extração de petróleo"
        assert cand.cnaes_secundarios == ["1922501"]
        assert cand.source == "receita_cnpj"
        assert cand.source_snapshot == "2026-08"
        assert result.has_more is False
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_cnpj_invalido_retorna_vazio_sem_erro():
    from services.registry.search import RegistrySearchService, SearchFilters

    engine, db = _db()
    try:
        _seed(db)
        result = RegistrySearchService(db).search(SearchFilters(cnpj="123"))
        assert result.items == []
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_filtros_combinados_e_paginacao_keyset():
    from services.registry.search import RegistrySearchService, SearchFilters

    engine, db = _db()
    try:
        _seed(db)
        svc = RegistrySearchService(db)
        page1 = svc.search(SearchFilters(uf="RJ", situacao="2", limit=1))
        assert len(page1.items) == 1
        assert page1.has_more is True
        assert page1.next_cursor is not None
        page2 = svc.search(SearchFilters(uf="RJ", situacao="2", limit=1, cursor=page1.next_cursor))
        assert len(page2.items) == 1
        assert page2.has_more is False
        assert page1.items[0].cnpj != page2.items[0].cnpj
        assert page1.items[0].cnpj < page2.items[0].cnpj
        baixada = svc.search(SearchFilters(situacao="08"))
        assert [c.cnpj for c in baixada.items] == ["60701190000104"]
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_cnae_secundario_encontrado_via_assoc():
    from services.registry.search import RegistrySearchService, SearchFilters

    engine, db = _db()
    try:
        _seed(db)
        result = RegistrySearchService(db).search(SearchFilters(cnaes=["1922501"]))
        assert [c.cnpj for c in result.items] == ["33000167000101"]
        principal = RegistrySearchService(db).search(SearchFilters(cnaes=["6421200"]))
        assert [c.cnpj for c in principal.items] == ["60701190000104"]
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_limite_e_capped_e_busca_sem_n_plus_1():
    from services.registry.search import RegistrySearchService, SearchFilters

    engine, db = _db()
    try:
        _seed(db)
        queries: list[str] = []

        def counter(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement[:60])

        event.listen(engine, "before_cursor_execute", counter)
        try:
            result = RegistrySearchService(db).search(SearchFilters(limit=1000))
        finally:
            event.remove(engine, "before_cursor_execute", counter)
        assert len(result.items) == 3
        assert len(queries) <= 4
        with pytest.raises(ValueError):
            SearchFilters(limit=0)
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()


def test_candidate_nao_e_company():
    from database.models import RegistryCompany
    from services.registry.candidate import RegistryCandidate

    assert not hasattr(RegistryCompany, "organization_id")
    assert "organization_id" not in RegistryCandidate.__dataclass_fields__
    assert RegistryCandidate.__module__ != RegistryCompany.__module__


def test_provenance_sem_observed_at_fabricado():
    from services.registry.search import RegistrySearchService, SearchFilters

    engine, db = _db()
    try:
        _seed(db)
        cand = RegistrySearchService(db).search(
            SearchFilters(cnpj="33000167000101")).items[0]
        assert cand.source == "receita_cnpj"
        assert cand.source_snapshot == "2026-08"
        assert cand.observed_at is None
        assert cand.imported_at is not None
        assert cand.provenance == {"source": "receita_cnpj", "source_snapshot": "2026-08"}
    finally:
        _cleanup(db)
        db.close()
        engine.dispose()
