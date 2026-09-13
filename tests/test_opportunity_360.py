"""Contratos da leitura Opportunity 360.

Os testes de persistência usam PostgreSQL real quando disponível. A suíte
unitária sempre cobre ordenação determinística da timeline.
"""
from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from db_reachable import database_url, is_database_reachable
from database.engagement_models import CommercialTask
from database.models import Base, Lead, Organization
from services.prospecting.lead_opportunity_service import LeadOpportunityService
from services.prospecting.offer_matcher import LeadOpportunity
from src.services.opportunity_360_service import Opportunity360Service, sort_timeline


class TestTimelineOrdering:
    def test_mais_recente_primeiro_e_desempate_deterministico(self):
        items = [
            {"type": "TASK", "occurred_at": "2026-09-12T10:00:00+00:00", "source_entity": "task:b"},
            {"type": "ACTIVITY", "occurred_at": "2026-09-13T10:00:00+00:00", "source_entity": "activity:z"},
            {"type": "TASK", "occurred_at": "2026-09-12T10:00:00+00:00", "source_entity": "task:a"},
            {"type": "ACTIVITY", "occurred_at": None, "source_entity": "activity:old"},
        ]

        ordered = sort_timeline(items)

        assert [item["source_entity"] for item in ordered] == [
            "activity:z",
            "task:a",
            "task:b",
            "activity:old",
        ]


DB_URL = database_url()
_persistencia = pytest.mark.skipif(
    not is_database_reachable(DB_URL),
    reason="Postgres indisponivel - Opportunity 360 requer persistencia real",
)


@pytest.fixture()
def db_session():
    engine = create_engine(DB_URL)
    # Importar engagement_models acima registra as tabelas no mesmo metadata.
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
        slug=f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}",
    )


def _lead(org: Organization, company: str) -> Lead:
    return Lead(
        id=uuid.uuid4(),
        organization_id=org.id,
        company_name=company,
        city="São Paulo",
        state="SP",
    )


def _persist_opportunity(db, lead: Lead, offer_key: str = "trophies"):
    service = LeadOpportunityService()
    service.persist_opportunities(
        db,
        lead,
        [
            LeadOpportunity(
                offer_key=offer_key,
                profile_key="test-profile",
                score=82,
                offer_version="1.0",
                evidence=["evidência real de teste"],
                signals_matched=["EVENT_UPCOMING"],
                signals_missing=[],
            )
        ],
    )
    db.flush()
    return service.list_for_lead(db, lead.id)[0]


@_persistencia
class TestOpportunity360Persistence:
    def test_workspace_b_nao_consulta_oportunidade_do_workspace_a(self, db_session):
        db, _engine = db_session
        org_a, org_b = _org("Workspace A"), _org("Workspace B")
        db.add_all([org_a, org_b])
        db.flush()
        lead_a = _lead(org_a, "Empresa A")
        lead_b = _lead(org_b, "Empresa B")
        db.add_all([lead_a, lead_b])
        db.flush()
        opportunity_a = _persist_opportunity(db, lead_a)
        opportunity_b = _persist_opportunity(db, lead_b)

        assert Opportunity360Service(db, org_b.id).get(opportunity_a.id) is None
        own = Opportunity360Service(db, org_b.id).get(opportunity_b.id)
        assert own is not None
        assert own["lead"]["company_name"] == "Empresa B"

    def test_relacoes_tambem_respeitam_organization_id(self, db_session):
        db, _engine = db_session
        org_a, org_b = _org("Tenant A"), _org("Tenant B")
        db.add_all([org_a, org_b])
        db.flush()
        lead_b = _lead(org_b, "Empresa Segura")
        db.add(lead_b)
        db.flush()
        opportunity_b = _persist_opportunity(db, lead_b)

        # Linha propositalmente inconsistente: FK aponta para lead de B, mas a
        # própria tarefa pertence a A. A composição precisa falhar fechada.
        db.add(CommercialTask(
            organization_id=org_a.id,
            lead_id=lead_b.id,
            task_type="CALL",
            title="Não pode vazar",
            status="OPEN",
            source="test",
            idempotency_key=f"cross-tenant:{uuid.uuid4()}",
        ))
        db.flush()

        payload = Opportunity360Service(db, org_b.id).get(opportunity_b.id)
        assert payload is not None
        assert payload["tasks"] == []
        assert all(item["title"] != "Não pode vazar" for item in payload["timeline"])

    def test_dados_parciais_nao_quebram_a_visao(self, db_session):
        db, _engine = db_session
        org = _org("Parcial")
        db.add(org)
        db.flush()
        lead = _lead(org, "Empresa com poucos dados")
        db.add(lead)
        db.flush()
        opportunity = _persist_opportunity(db, lead, offer_key="mechanical_project")

        payload = Opportunity360Service(db, org.id).get(opportunity.id)

        assert payload is not None
        assert payload["company"]["name"] == "Empresa com poucos dados"
        assert payload["decision_maker"] is None
        assert payload["owner"] is None
        assert payload["next_action"] is None
        assert payload["capabilities"]["read_only"] is True

    def test_numero_de_queries_permanece_limitado_com_muitas_tarefas(self, db_session):
        db, engine = db_session
        org = _org("Performance")
        db.add(org)
        db.flush()
        lead = _lead(org, "Empresa Performática")
        db.add(lead)
        db.flush()
        opportunity = _persist_opportunity(db, lead)
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
                idempotency_key=f"perf:{uuid.uuid4()}",
            )
            for index in range(30)
        ])
        db.flush()

        statements = 0

        def count_queries(*_args, **_kwargs):
            nonlocal statements
            statements += 1

        event.listen(engine, "before_cursor_execute", count_queries)
        try:
            payload = Opportunity360Service(db, org.id).get(opportunity.id)
        finally:
            event.remove(engine, "before_cursor_execute", count_queries)

        assert payload is not None
        assert len(payload["tasks"]) == 30
        # O volume de relações aumenta linhas, não round-trips. Mantemos uma
        # margem explícita para as fontes agregadas desta fatia.
        assert statements <= 16
