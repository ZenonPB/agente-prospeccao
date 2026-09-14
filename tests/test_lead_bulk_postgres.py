"""Provas PostgreSQL reais para idempotência/locking do bulk comercial."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.services.lead_bulk_command_service import LeadBulkCommandService


E2E_DATABASE_URL = os.environ.get("E2E_DATABASE_URL")
pytestmark = pytest.mark.skipif(not E2E_DATABASE_URL, reason="E2E_DATABASE_URL não definido")


@pytest.fixture()
def bulk_scenario():
    from database.models import (
        CommercialBulkOperation,
        Lead,
        LeadActivity,
        LeadStatus,
        Organization,
        OrganizationMember,
        SalesRole,
        User,
    )

    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    suffix = uuid.uuid4().hex[:10]
    org = Organization(name=f"Bulk E2E {suffix}", slug=f"bulk-e2e-{suffix}")
    user = User(email=f"bulk-{suffix}@test.local", password_hash="test", name="Bulk E2E")
    db.add_all([org, user])
    db.flush()
    member = OrganizationMember(organization_id=org.id, user_id=user.id, sales_role=SalesRole.MANAGER)
    db.add(member)
    lead = Lead(
        organization_id=org.id,
        place_id=f"bulk-e2e-{suffix}",
        name="Empresa Bulk",
        company_name="Empresa Bulk",
        city="Araraquara",
        state="SP",
        country="Brasil",
        status=LeadStatus.NOVO,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    snapshot = {
        "org_id": org.id,
        "user_id": user.id,
        "lead_id": lead.id,
        "expected": lead.updated_at.astimezone(timezone.utc).isoformat(),
        "Session": Session,
    }
    db.close()
    try:
        yield snapshot
    finally:
        cleanup = Session()
        cleanup.query(LeadActivity).filter(LeadActivity.lead_id == lead.id).delete(synchronize_session=False)
        cleanup.query(CommercialBulkOperation).filter(CommercialBulkOperation.organization_id == org.id).delete(synchronize_session=False)
        cleanup.query(Lead).filter(Lead.id == lead.id).delete(synchronize_session=False)
        cleanup.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).delete(synchronize_session=False)
        cleanup.query(Organization).filter(Organization.id == org.id).delete(synchronize_session=False)
        cleanup.query(User).filter(User.id == user.id).delete(synchronize_session=False)
        cleanup.commit()
        cleanup.close()
        engine.dispose()


def _execute_same_bulk(scenario, key: str):
    from database.models import OrganizationMember, User

    db = scenario["Session"]()
    try:
        member = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == scenario["org_id"],
            OrganizationMember.user_id == scenario["user_id"],
        ).one()
        user = db.query(User).filter(User.id == scenario["user_id"]).one()
        service = LeadBulkCommandService(db, scenario["org_id"], member, user)
        return service.execute(
            {
                "operation": "status",
                "lead_ids": [str(scenario["lead_id"])],
                "status": "CONTATADO",
                "lost_reason": None,
                "assigned_to_id": None,
                "expected_updated_at": {str(scenario["lead_id"]): scenario["expected"]},
            },
            key,
        )
    finally:
        db.close()


def test_bulk_mesma_chave_concorrente_produz_um_unico_efeito(bulk_scenario):
    from database.models import CommercialBulkOperation, Lead, LeadActivity, LeadActivityAction, LeadStatus

    key = f"bulk-e2e-{uuid.uuid4()}"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _execute_same_bulk(bulk_scenario, key), range(2)))

    assert sorted(item["replayed"] for item in results) == [False, True]
    assert {item["accepted"] for item in results} == {1}

    db = bulk_scenario["Session"]()
    try:
        assert db.query(CommercialBulkOperation).filter(
            CommercialBulkOperation.organization_id == bulk_scenario["org_id"],
            CommercialBulkOperation.idempotency_key == key,
        ).count() == 1
        lead = db.query(Lead).filter(Lead.id == bulk_scenario["lead_id"]).one()
        assert lead.status == LeadStatus.CONTATADO
        # CONTATADO gera duas atividades canônicas (mudança + semântica), mas
        # cada uma deve existir uma única vez apesar das duas requests.
        activities = db.query(LeadActivity).filter(LeadActivity.lead_id == lead.id).all()
        assert len(activities) == 2
        actions = [item.action for item in activities]
        assert actions.count(LeadActivityAction.STATUS_CHANGED) == 1
        assert len(set(actions)) == 2
    finally:
        db.close()


def test_bulk_sem_expected_updated_at_falha_fechado_no_postgres(bulk_scenario):
    from database.models import OrganizationMember, User, Lead, LeadStatus

    db = bulk_scenario["Session"]()
    try:
        member = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == bulk_scenario["org_id"],
            OrganizationMember.user_id == bulk_scenario["user_id"],
        ).one()
        user = db.query(User).filter(User.id == bulk_scenario["user_id"]).one()
        service = LeadBulkCommandService(db, bulk_scenario["org_id"], member, user)
        preview = service.preview({
            "operation": "status",
            "lead_ids": [str(bulk_scenario["lead_id"])],
            "status": "CONTATADO",
            "lost_reason": None,
            "assigned_to_id": None,
            "expected_updated_at": {},
        })
        assert preview["accepted_ids"] == []
        assert preview["rejected"][0]["reason"] == "VERSION_CONFLICT"
        lead = db.query(Lead).filter(Lead.id == bulk_scenario["lead_id"]).one()
        assert lead.status == LeadStatus.NOVO
    finally:
        db.close()
