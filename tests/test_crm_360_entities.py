"""Invariantes das visões Company 360 e Person 360."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from db_reachable import database_url, is_database_reachable
from database.engagement_models import CommercialTask
from database.models import Base, Company, Lead, Organization, Person
from services.prospecting.lead_opportunity_service import LeadOpportunityService
from services.prospecting.offer_matcher import LeadOpportunity
from src.services.crm_360_service import Crm360Service


DB_URL = database_url()
_persistencia = pytest.mark.skipif(
    not is_database_reachable(DB_URL),
    reason="Postgres indisponivel - CRM 360 requer persistencia real",
)


@pytest.fixture()
def db_session():
    engine = create_engine(DB_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session, engine
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def _org(name: str) -> Organization:
    return Organization(
        id=uuid.uuid4(),
        name=name,
        slug=f"crm360-{uuid.uuid4().hex[:10]}",
    )


def _account(db, org: Organization, name: str):
    company = Company(
        id=uuid.uuid4(), organization_id=org.id, company_name=name,
        name=name, city="Araraquara", state="SP",
    )
    db.add(company)
    db.flush()
    person = Person(
        id=uuid.uuid4(), organization_id=org.id, company_id=company.id,
        name=f"Decisor {name}", email=f"{uuid.uuid4().hex[:8]}@example.com",
        routable=True, contact_confidence=80, identity_confidence=90,
    )
    db.add(person)
    db.flush()
    lead = Lead(
        id=uuid.uuid4(), organization_id=org.id, company_id=company.id,
        primary_person_id=person.id, company_name=name, city="Araraquara", state="SP",
    )
    db.add(lead)
    db.flush()
    LeadOpportunityService().persist_opportunities(
        db,
        lead,
        [LeadOpportunity(
            offer_key="landing_page", profile_key="test", score=75,
            offer_version="1.0", evidence=["fact"], signals_matched=["HAS_PHONE"],
            signals_missing=[],
        )],
    )
    db.flush()
    return company, person, lead


@_persistencia
class TestCrm360Entities:
    def test_company_e_person_nao_vazam_entre_workspaces(self, db_session):
        db, _engine = db_session
        org_a, org_b = _org("A"), _org("B")
        db.add_all([org_a, org_b])
        db.flush()
        company_a, person_a, _ = _account(db, org_a, "Empresa A")
        company_b, person_b, _ = _account(db, org_b, "Empresa B")

        service_b = Crm360Service(db, org_b.id)
        assert service_b.company(company_a.id) is None
        assert service_b.person(person_a.id) is None
        assert service_b.company(company_b.id)["company"]["company_name"] == "Empresa B"
        assert service_b.person(person_b.id)["person"]["name"] == "Decisor Empresa B"

    def test_company_com_dados_parciais_responde_normalmente(self, db_session):
        db, _engine = db_session
        org = _org("Parcial")
        db.add(org)
        db.flush()
        company = Company(
            id=uuid.uuid4(), organization_id=org.id, company_name="Conta Parcial",
        )
        lead = Lead(
            id=uuid.uuid4(), organization_id=org.id, company_id=company.id,
            company_name="Conta Parcial", city="Araraquara",
        )
        db.add_all([company, lead])
        db.flush()

        payload = Crm360Service(db, org.id).company(company.id)

        assert payload is not None
        assert payload["company"]["company_name"] == "Conta Parcial"
        assert payload["persons"] == []
        assert payload["opportunities"] == []
        assert payload["capabilities"]["read_only"] is True

    def test_relacao_com_tenant_inconsistente_nao_vaza(self, db_session):
        db, _engine = db_session
        org_a, org_b = _org("Tenant A"), _org("Tenant B")
        db.add_all([org_a, org_b])
        db.flush()
        company_b, _person_b, lead_b = _account(db, org_b, "Conta B")
        db.add(CommercialTask(
            organization_id=org_a.id,
            lead_id=lead_b.id,
            task_type="CALL",
            title="Segredo A",
            status="OPEN",
            source="test",
            idempotency_key=f"crm360-cross:{uuid.uuid4()}",
        ))
        db.flush()

        payload = Crm360Service(db, org_b.id).company(company_b.id)
        assert payload is not None
        assert all(task["title"] != "Segredo A" for task in payload["tasks"])
        assert all(item["title"] != "Segredo A" for item in payload["timeline"])

    def test_query_count_company_nao_cresce_com_volume_de_tarefas(self, db_session):
        db, engine = db_session
        org = _org("Performance")
        db.add(org)
        db.flush()
        company, _person, lead = _account(db, org, "Conta Performance")
        now = datetime.now(timezone.utc)
        db.add_all([
            CommercialTask(
                organization_id=org.id,
                lead_id=lead.id,
                task_type="CALL",
                title=f"Tarefa {index}",
                due_at=now + timedelta(days=index),
                status="OPEN",
                source="test",
                idempotency_key=f"crm360-perf:{uuid.uuid4()}",
            )
            for index in range(40)
        ])
        db.flush()

        statements = 0
        def count_queries(*_args, **_kwargs):
            nonlocal statements
            statements += 1

        event.listen(engine, "before_cursor_execute", count_queries)
        try:
            payload = Crm360Service(db, org.id).company(company.id)
        finally:
            event.remove(engine, "before_cursor_execute", count_queries)

        assert payload is not None
        assert len(payload["tasks"]) == 40
        assert statements <= 10
