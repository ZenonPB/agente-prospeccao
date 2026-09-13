"""Invariantes de escrita da Opportunity 360.

A suíte usa PostgreSQL real quando disponível porque autorização, FKs,
constraints e idempotência são parte do contrato desta fatia de CRM.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_reachable import database_url, is_database_reachable
from database.engagement_models import CommercialTask
from database.models import (
    Base,
    Lead,
    LeadStatus,
    LostReason,
    NegotiationStage,
    Organization,
    OrganizationMember,
    OrganizationRole,
    SalesRole,
    User,
)
from services.prospecting.lead_opportunity_service import LeadOpportunityService
from services.prospecting.offer_matcher import LeadOpportunity
from src.services.opportunity_command_service import (
    OpportunityCommandService,
    OpportunityForbidden,
    OpportunityNotFound,
    OpportunityValidation,
)


DB_URL = database_url()
_persistencia = pytest.mark.skipif(
    not is_database_reachable(DB_URL),
    reason="Postgres indisponivel - comandos Opportunity 360 requerem persistencia real",
)


@pytest.fixture()
def db_session():
    engine = create_engine(DB_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def _org(label: str) -> Organization:
    return Organization(
        id=uuid.uuid4(),
        name=label,
        slug=f"{label.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}",
    )


def _user(label: str) -> User:
    suffix = uuid.uuid4().hex[:8]
    return User(
        id=uuid.uuid4(),
        email=f"{label.lower()}-{suffix}@example.test",
        password_hash="test-only",
        name=label,
    )


def _member(org, user, *, role=OrganizationRole.MEMBER, sales_role=SalesRole.CONSULTOR):
    return OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role=role,
        sales_role=sales_role,
    )


def _opportunity(db, lead: Lead):
    service = LeadOpportunityService()
    service.persist_opportunities(
        db,
        lead,
        [LeadOpportunity(
            offer_key="landing_page",
            profile_key="test-profile",
            score=84,
            offer_version="1.0",
            evidence=["teste"],
            signals_matched=["NO_WEBSITE"],
            signals_missing=[],
        )],
    )
    db.flush()
    return service.list_for_lead(db, lead.id)[0]


def _scenario(db, *, sales_role=SalesRole.MANAGER, role=OrganizationRole.OWNER):
    org = _org("Workspace Commands")
    actor = _user("Actor")
    db.add_all([org, actor])
    db.flush()
    member = _member(org, actor, role=role, sales_role=sales_role)
    db.add(member)
    lead = Lead(
        id=uuid.uuid4(),
        organization_id=org.id,
        company_name="Empresa Teste",
        city="Araraquara",
        state="SP",
        status=LeadStatus.QUALIFICADO,
    )
    db.add(lead)
    db.flush()
    opportunity = _opportunity(db, lead)
    # Os testes de validação exercitam rollback. Persistimos o cenário base
    # primeiro para que o rollback reverta somente a operação sob teste, como
    # acontece numa request real contra entidades já existentes.
    db.commit()
    opportunity = LeadOpportunityService().list_for_lead(db, lead.id)[0]
    return org, actor, member, lead, opportunity


@_persistencia
class TestOpportunityCommandPersistence:
    def test_manager_edita_campos_canonicos_e_audita(self, db_session):
        db = db_session
        org, actor, member, lead, opportunity = _scenario(db)
        service = OpportunityCommandService(db, org.id, member, actor)

        result = service.update(opportunity.id, {
            "status": "RESPONDIDO",
            "negotiation_stage": "RD",
            "value": 7200,
            "expected_close_date": "2026-10-20T12:00:00Z",
            "next_action_at": "2026-09-15T13:30:00-03:00",
            "notes": "Cliente pediu reunião com engenharia.",
        })

        db.refresh(lead)
        assert result["commercial"]["status"] == "RESPONDIDO"
        assert lead.status == LeadStatus.RESPONDIDO
        assert lead.negotiation_stage == NegotiationStage.RD
        assert float(lead.value) == 7200
        assert lead.notes == "Cliente pediu reunião com engenharia."
        assert lead.expected_close_date.tzinfo is not None
        assert lead.next_action_at.tzinfo is not None
        assert result["changed"]["value"] == 7200

    def test_perda_exige_motivo_e_persiste_motivo_valido(self, db_session):
        db = db_session
        org, actor, member, lead, opportunity = _scenario(db)
        opportunity_id = opportunity.id
        service = OpportunityCommandService(db, org.id, member, actor)

        with pytest.raises(OpportunityValidation, match="motivo da perda"):
            service.update(opportunity_id, {"status": "PERDIDO"})
        db.rollback()

        result = service.update(opportunity_id, {
            "status": "PERDIDO",
            "lost_reason": "PRECO",
        })
        db.refresh(lead)
        assert result["commercial"]["status"] == "PERDIDO"
        assert lead.lost_reason == LostReason.PRECO

    def test_analyst_permanece_read_only(self, db_session):
        db = db_session
        org, actor, member, _lead, opportunity = _scenario(
            db,
            sales_role=SalesRole.ANALYST,
            role=OrganizationRole.MEMBER,
        )
        service = OpportunityCommandService(db, org.id, member, actor)
        with pytest.raises(OpportunityForbidden):
            service.update(opportunity.id, {"value": 100})
        with pytest.raises(OpportunityForbidden):
            service.create_task(opportunity.id, {
                "client_request_id": "analyst-123",
                "title": "Não deve criar",
            })

    def test_consultor_nao_toma_carteira_de_colega(self, db_session):
        db = db_session
        org, actor, member, lead, opportunity = _scenario(
            db,
            sales_role=SalesRole.CONSULTOR,
            role=OrganizationRole.MEMBER,
        )
        other = _user("Outro consultor")
        db.add(other)
        db.flush()
        db.add(_member(org, other))
        lead.assigned_to_id = other.id
        db.commit()

        service = OpportunityCommandService(db, org.id, member, actor)
        with pytest.raises(OpportunityNotFound):
            service.update(opportunity.id, {"value": 1500})

    def test_owner_so_pode_atribuir_membro_do_workspace(self, db_session):
        db = db_session
        org, actor, member, _lead, opportunity = _scenario(db)
        foreign_org = _org("Foreign")
        foreign_user = _user("Foreign User")
        db.add_all([foreign_org, foreign_user])
        db.flush()
        db.add(_member(foreign_org, foreign_user))
        db.commit()

        service = OpportunityCommandService(db, org.id, member, actor)
        with pytest.raises(OpportunityValidation, match="workspace"):
            service.update(opportunity.id, {"owner_user_id": str(foreign_user.id)})

    def test_criacao_de_tarefa_e_idempotente_por_request_id(self, db_session):
        db = db_session
        org, actor, member, lead, opportunity = _scenario(db)
        service = OpportunityCommandService(db, org.id, member, actor)
        payload = {
            "client_request_id": "task-request-001",
            "title": "Preparar proposta técnica",
            "description": "Revisar escopo antes da reunião.",
            "task_type": "FOLLOW_UP",
            "due_at": "2026-09-20T12:00:00Z",
        }

        first = service.create_task(opportunity.id, payload)
        second = service.create_task(opportunity.id, payload)

        assert first["created"] is True
        assert second["created"] is False
        assert first["id"] == second["id"]
        assert db.query(CommercialTask).filter(
            CommercialTask.organization_id == org.id,
            CommercialTask.lead_id == lead.id,
            CommercialTask.source == "opportunity360",
        ).count() == 1

    def test_update_task_rejeita_task_de_outro_lead(self, db_session):
        db = db_session
        org, actor, member, _lead, opportunity = _scenario(db)
        foreign_lead = Lead(
            id=uuid.uuid4(),
            organization_id=org.id,
            company_name="Outro lead",
        )
        db.add(foreign_lead)
        db.flush()
        task = CommercialTask(
            organization_id=org.id,
            lead_id=foreign_lead.id,
            task_type="CALL",
            title="Outra tarefa",
            status="OPEN",
            source="test",
            idempotency_key=f"test:{uuid.uuid4()}",
        )
        db.add(task)
        db.commit()

        service = OpportunityCommandService(db, org.id, member, actor)
        with pytest.raises(OpportunityNotFound):
            service.update_task(opportunity.id, task.id, {"status": "COMPLETED"})

    def test_datas_invalidas_falham_sem_commit(self, db_session):
        db = db_session
        org, actor, member, lead, opportunity = _scenario(db)
        lead_id = lead.id
        opportunity_id = opportunity.id
        original = lead.next_action_at
        service = OpportunityCommandService(db, org.id, member, actor)

        with pytest.raises(OpportunityValidation, match="Data/hora inválida"):
            service.update(opportunity_id, {"next_action_at": "13/09/2026 10h"})
        db.rollback()
        persisted = db.query(Lead).filter(Lead.id == lead_id).one()
        assert persisted.next_action_at == original
