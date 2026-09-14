"""Contrato do Sales Operating System (Bloco B)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_reachable import database_url, is_database_reachable

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)
DB_URL = database_url()


def test_saved_filter_normalization_is_allowlisted_and_deterministic():
    from src.services.sales_operating_service import SalesOperatingValidation, normalize_saved_filters

    assert normalize_saved_filters({
        "status": ["QUALIFICADO", "QUALIFICADO", "CONTATADO"],
        "state": " sp ",
        "search": " clínica ",
        "cursor": None,
    }) == {
        "search": "clínica",
        "state": "sp",
        "status": ["CONTATADO", "QUALIFICADO"],
    }
    with pytest.raises(SalesOperatingValidation):
        normalize_saved_filters({"sql": "drop table leads"})


def test_bulk_task_contract_is_supported_without_relaxing_version_gate():
    from src.services.lead_bulk_command_service import normalize_bulk_payload

    lead_id = str(uuid.uuid4())
    normalized = normalize_bulk_payload({
        "operation": "create_task",
        "lead_ids": [lead_id],
        "expected_updated_at": {lead_id: "2026-09-14T12:00:00+00:00"},
        "task_type": "follow_up",
        "task_title": "Retomar orçamento",
        "task_due_at": "2026-09-15T12:00:00Z",
    })
    assert normalized["operation"] == "create_task"
    assert normalized["task_type"] == "FOLLOW_UP"
    assert normalized["task_title"] == "Retomar orçamento"
    assert lead_id in normalized["expected_updated_at"]


@pytest.mark.skipif(not is_database_reachable(DB_URL), reason="Postgres indisponível")
def test_operating_queue_search_saved_view_and_tenant_isolation_postgres():
    from database.crm_models import CommercialSavedView
    from database.engagement_models import CommercialTask, NextBestActionDecision
    from src.db.models import (
        Company, Lead, LeadOpportunityRow, LeadStatus, Organization,
        OrganizationMember, OrganizationRole, SalesRole, User,
    )
    from src.services.sales_operating_service import SalesOperatingService

    engine = create_engine(DB_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    token = uuid.uuid4().hex[:8]
    org_a = Organization(name="CRM A", slug=f"crm-a-{token}")
    org_b = Organization(name="CRM B", slug=f"crm-b-{token}")
    user = User(email=f"crm-{token}@example.com", password_hash="x", name="Consultor CRM")
    db.add_all([org_a, org_b, user])
    db.flush()
    member = OrganizationMember(
        organization_id=org_a.id,
        user_id=user.id,
        role=OrganizationRole.OWNER,
        sales_role=SalesRole.MANAGER,
    )
    db.add(member)
    company_a = Company(organization_id=org_a.id, company_name="Alpha Cliente", city="Araraquara")
    company_b = Company(organization_id=org_b.id, company_name="Alpha Segredo", city="São Carlos")
    db.add_all([company_a, company_b])
    db.flush()
    lead_a = Lead(
        organization_id=org_a.id,
        company_id=company_a.id,
        company_name="Alpha Cliente",
        city="Araraquara",
        status=LeadStatus.QUALIFICADO,
        qualification_score=91,
        assigned_to_id=user.id,
        next_action_at=datetime.now(timezone.utc) - timedelta(hours=2),
        updated_at=datetime.now(timezone.utc),
    )
    lead_b = Lead(
        organization_id=org_b.id,
        company_id=company_b.id,
        company_name="Alpha Segredo",
        city="São Carlos",
        status=LeadStatus.QUALIFICADO,
        qualification_score=99,
        updated_at=datetime.now(timezone.utc),
    )
    db.add_all([lead_a, lead_b])
    db.flush()
    db.add(LeadOpportunityRow(
        organization_id=org_a.id, lead_id=lead_a.id, offer_key="landing_page", score=93,
    ))
    db.add(CommercialTask(
        organization_id=org_a.id, lead_id=lead_a.id, owner_user_id=user.id,
        task_type="FOLLOW_UP", title="Retomar proposta",
        due_at=datetime.now(timezone.utc) - timedelta(hours=1),
        status="OPEN", source="test", idempotency_key=f"test-{token}",
    ))
    db.add(NextBestActionDecision(
        organization_id=org_a.id, lead_id=lead_a.id, action="Ligar para o decisor",
        why="Há proposta sem retorno", confidence=0.9, evidence=[],
        offer_key="landing_page", fingerprint=uuid.uuid4().hex, status="PENDING",
    ))
    db.commit()

    try:
        service = SalesOperatingService(db, org_a.id, member, user)
        queue = service.queue()
        assert queue["items"][0]["lead_id"] == str(lead_a.id)
        assert "Tarefa vencida" in queue["items"][0]["reasons"]
        assert queue["items"][0]["recommended_action"] == "Ligar para o decisor"

        search = service.search("Alpha")
        company_titles = [item["title"] for item in search["groups"]["companies"]]
        assert "Alpha Cliente" in company_titles
        assert "Alpha Segredo" not in company_titles

        saved = service.create_saved_view(
            name="Aptos SP", view_kind="analytics",
            filters={"status": ["QUALIFICADO"], "state": "SP"}, shared=True,
        )
        assert saved.organization_id == org_a.id
        assert service.list_saved_views("analytics")[0].id == saved.id
    finally:
        db.rollback()
        db.query(CommercialSavedView).filter(CommercialSavedView.organization_id == org_a.id).delete(synchronize_session=False)
        db.query(NextBestActionDecision).filter(NextBestActionDecision.organization_id == org_a.id).delete(synchronize_session=False)
        db.query(CommercialTask).filter(CommercialTask.organization_id == org_a.id).delete(synchronize_session=False)
        db.query(LeadOpportunityRow).filter(LeadOpportunityRow.organization_id == org_a.id).delete(synchronize_session=False)
        db.query(Lead).filter(Lead.organization_id.in_([org_a.id, org_b.id])).delete(synchronize_session=False)
        db.query(Company).filter(Company.organization_id.in_([org_a.id, org_b.id])).delete(synchronize_session=False)
        db.query(OrganizationMember).filter(OrganizationMember.organization_id == org_a.id).delete(synchronize_session=False)
        db.query(Organization).filter(Organization.id.in_([org_a.id, org_b.id])).delete(synchronize_session=False)
        db.query(User).filter(User.id == user.id).delete(synchronize_session=False)
        db.commit()
        db.close()
