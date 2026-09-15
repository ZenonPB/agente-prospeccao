"""Registry no contrato federado + isolamento do CRM (PG real).

Pula sem E2E_DATABASE_URL.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

E2E_DATABASE_URL = os.environ.get("E2E_DATABASE_URL")
pytestmark = pytest.mark.skipif(not E2E_DATABASE_URL, reason="E2E_DATABASE_URL não definido")


def _db():
    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)()


def _seed_registry(db):
    from database.models import RegistryCompany

    db.add(RegistryCompany(
        cnpj="33000167000101", cnpj_basico="33000167",
        razao_social="PETROLEO BRASILEIRO S A PETROBRAS",
        matriz=True, situacao="2", cnae_principal="6000001",
        uf="RJ", municipio_cod="6001",
        source="receita_cnpj", source_snapshot="2026-08"))
    db.commit()


def _cleanup_registry(db):
    from database.models import RegistryCompany, RegistryCompanyCnae

    db.query(RegistryCompanyCnae).delete(synchronize_session=False)
    db.query(RegistryCompany).filter(
        RegistryCompany.cnpj.in_(["33000167000101", "60701190000104"])).delete(
        synchronize_session=False)
    db.commit()


def test_registry_provider_executa_free_only_sem_custo():
    import asyncio

    from services.prospecting.provider_access_policy import ProviderAccessPolicy
    from services.prospecting.provider_federation import FederatedProviderRegistry
    from services.registry.provider import RegistryDiscoveryProvider

    engine, db = _db()
    try:
        _seed_registry(db)
        registry = FederatedProviderRegistry()
        registry.register(RegistryDiscoveryProvider(db))
        result = asyncio.run(registry.collect(
            "company_registry", {"uf": "RJ"},
            access_policy=ProviderAccessPolicy(),
        ))
        assert result["status"] == "success"
        assert result["cost_spent"] == 0
        assert result["items"][0]["cnpj"] == "33000167000101"
        assert result["items"][0]["source"] == "brazil_company_registry"
        empty = asyncio.run(registry.collect(
            "company_registry", {"uf": "XX"},
            access_policy=ProviderAccessPolicy(),
        ))
        assert empty["status"] == "empty"
    finally:
        _cleanup_registry(db)
        db.close()
        engine.dispose()


def test_registry_nao_cria_company_lead_ou_oportunidade():
    """RegistryCandidate != Company: ingestão + busca não tocam o CRM."""
    import asyncio

    from database.models import Company, Lead, LeadOpportunityRow, Organization
    from services.registry.importer import RegistryFileSpec, RegistryImporter
    from services.registry.search import RegistrySearchService, SearchFilters

    engine, db = _db()
    suffix = uuid.uuid4().hex[:8]
    try:
        org = Organization(name=f"Reg Iso {suffix}", slug=f"reg-iso-{suffix}")
        db.add(org)
        db.flush()
        before = (
            db.query(Company).filter(Company.organization_id == org.id).count(),
            db.query(Lead).filter(Lead.organization_id == org.id).count(),
            db.query(LeadOpportunityRow).filter(
                LeadOpportunityRow.organization_id == org.id).count(),
        )
        import tempfile

        vals = ['"60701190"', '"0001"', '"04"', '"1"', '"ITAU"',
                '"2"', '"20200115"', '"00"', '""', '"105"', '"20100110"',
                '"6421200"', '""', '"RUA"', '"A"', '"10"', '""', '"B"',
                '"20031170"', '"SP"', '"7107"',
                '"11"', '"1"', '""', '""', '""', '""', '""', '""', '""']
        assert len(vals) == 30
        path = os.path.join(tempfile.mkdtemp(), "ESTABELE0")
        with open(path, "w", encoding="latin-1") as fh:
            fh.write(";".join(vals) + "\n")
        snap = RegistryImporter(db, batch_size=10).import_snapshot(
            snapshot_month="2026-08",
            files=[RegistryFileSpec(table_kind="estabelecimentos", path=path, file_name="ESTABELE0")],
        )
        assert snap.inserted == 1
        found = RegistrySearchService(db).search(SearchFilters(uf="SP"))
        assert any(c.cnpj == "60701190000104" for c in found.items)
        after = (
            db.query(Company).filter(Company.organization_id == org.id).count(),
            db.query(Lead).filter(Lead.organization_id == org.id).count(),
            db.query(LeadOpportunityRow).filter(
                LeadOpportunityRow.organization_id == org.id).count(),
        )
        assert after == before == (0, 0, 0)
    finally:
        from database.models import RegistryCompany, RegistryCompanyCnae, RegistryImportFile, RegistrySnapshot

        db.query(RegistryCompanyCnae).delete(synchronize_session=False)
        db.query(RegistryCompany).filter(
            RegistryCompany.cnpj.in_(["33000167000101", "60701190000104"])).delete(
            synchronize_session=False)
        db.query(RegistryImportFile).delete(synchronize_session=False)
        db.query(RegistrySnapshot).filter(RegistrySnapshot.snapshot_month == "2026-08").delete(
            synchronize_session=False)
        db.query(Organization).filter(Organization.id == org.id).delete(synchronize_session=False)
        db.commit()
        db.close()
        engine.dispose()
