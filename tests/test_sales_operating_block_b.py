"""Gates adicionais do Bloco B: CRM operacional, edição 360 e bulk global."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import uuid

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_reachable import database_url, is_database_reachable

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)
DB_URL = database_url()


def test_operating_bulk_normalization_is_fail_closed():
    from src.services.sales_operating_bulk_service import OperatingBulkValidation, normalize_operating_bulk_payload

    lead_id = str(uuid.uuid4())
    expected = {lead_id: "2026-09-14T12:00:00+00:00"}
    assert normalize_operating_bulk_payload({
        "operation": "add_tag", "lead_ids": [lead_id], "expected_updated_at": expected, "tag": "  Evento MEJ  ",
    })["tag"] == "Evento MEJ"
    assert normalize_operating_bulk_payload({
        "operation": "negotiation_stage", "lead_ids": [lead_id], "expected_updated_at": expected, "negotiation_stage": "RD",
    })["negotiation_stage"] == "RD"
    with pytest.raises(OperatingBulkValidation, match="todos os leads"):
        normalize_operating_bulk_payload({"operation": "archive", "lead_ids": [lead_id], "expected_updated_at": {}})
    with pytest.raises(OperatingBulkValidation, match="não permitido"):
        normalize_operating_bulk_payload({"operation": "archive", "lead_ids": [lead_id], "expected_updated_at": expected, "sql": "x"})


def test_saved_views_crm_accept_operational_filters_without_pagination():
    from src.services.sales_operating_service import normalize_saved_filters

    assert normalize_saved_filters({
        "search": " clínica ", "min_score": 75, "archived": "active", "tag": "MEJ", "offset": 100, "limit": 50,
    }) == {"archived": "active", "min_score": "75", "search": "clínica", "tag": "MEJ"}


def _entity_version(row) -> str:
    value = row.updated_at or row.created_at
    assert value is not None
    return value.isoformat()


@pytest.mark.skipif(not is_database_reachable(DB_URL), reason="Postgres indisponível")
def test_block_b_company_person_bulk_metadata_and_tenant_isolation_postgres():
    from database.crm_models import CrmEntityAudit, LeadCrmMetadata
    from database.engagement_models import SequenceEnrollment, SequenceExecution, SequenceTemplate
    from src.db.models import (
        Campaign, Company, ContactRole, Lead, LeadStatus, Organization,
        OrganizationMember, OrganizationRole, Person, SalesRole, User,
        CommercialBulkOperation,
    )
    from src.services.crm_entity_command_service import CrmEntityCommandService, CrmEntityConflict
    from src.services.sales_operating_bulk_service import SalesOperatingBulkService

    engine = create_engine(DB_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    token = uuid.uuid4().hex[:8]
    org_a = Organization(name="Bloco B A", slug=f"block-b-a-{token}")
    org_b = Organization(name="Bloco B B", slug=f"block-b-b-{token}")
    user = User(email=f"block-b-{token}@example.com", password_hash="x", name="Gestor B")
    db.add_all([org_a, org_b, user]); db.flush()
    member = OrganizationMember(organization_id=org_a.id, user_id=user.id, role=OrganizationRole.OWNER, sales_role=SalesRole.MANAGER)
    db.add(member)
    company_a = Company(organization_id=org_a.id, company_name="Empresa A", city="Araraquara")
    company_b = Company(organization_id=org_b.id, company_name="Empresa B", city="São Carlos")
    db.add_all([company_a, company_b]); db.flush()
    person_a = Person(organization_id=org_a.id, company_id=company_a.id, name="Maria A", role=ContactRole.OUTRO, email="maria@example.com")
    db.add(person_a); db.flush()
    campaign = Campaign(user_id=user.id, organization_id=org_a.id, name=f"Campanha {token}")
    db.add(campaign); db.flush()
    lead_a = Lead(organization_id=org_a.id, company_id=company_a.id, primary_person_id=person_a.id, company_name="Empresa A", status=LeadStatus.QUALIFICADO, qualification_score=88, assigned_to_id=user.id, updated_at=datetime.now(timezone.utc))
    lead_b = Lead(organization_id=org_b.id, company_id=company_b.id, company_name="Empresa B", status=LeadStatus.QUALIFICADO, qualification_score=99, updated_at=datetime.now(timezone.utc))
    db.add_all([lead_a, lead_b]); db.flush()
    sequence = SequenceTemplate(organization_id=org_a.id, name=f"Seq {token}", version=1, enabled=True, steps=[{"type": "CALL", "delay_minutes": 0, "title": "Ligar"}], created_by_id=user.id)
    db.add(sequence); db.commit()
    db.refresh(company_a); db.refresh(person_a); db.refresh(lead_a)

    try:
        commands = CrmEntityCommandService(db, org_a.id, member, user)
        old_company_version = _entity_version(company_a)
        updated_company = commands.update_company(company_a.id, expected_updated_at=old_company_version, values={"company_name": "Empresa A Editada", "website": "https://empresa-a.example.com"})
        assert updated_company.company_name == "Empresa A Editada"
        assert updated_company.normalized_domain == "empresa-a.example.com"
        with pytest.raises(CrmEntityConflict):
            commands.update_company(company_a.id, expected_updated_at=old_company_version, values={"city": "Matão"})

        updated_person = commands.update_person(person_a.id, expected_updated_at=_entity_version(person_a), values={"role_label": "Diretora Comercial", "routable": True})
        assert updated_person.role_label == "Diretora Comercial"
        verified = commands.human_verify_person(person_a.id, expected_updated_at=_entity_version(updated_person))
        assert verified.verification_status == "human_verified"
        assert verified.last_verified_at is not None

        db.refresh(lead_a)
        bulk = SalesOperatingBulkService(db, org_a.id, member, user)
        base = {"lead_ids": [str(lead_a.id)], "expected_updated_at": {str(lead_a.id): lead_a.updated_at.isoformat()}}
        first = bulk.execute({**base, "operation": "add_tag", "tag": "MEJ"}, f"tag-{token}-idem")
        assert first["summary"]["accepted"] == 1
        replay = bulk.execute({**base, "operation": "add_tag", "tag": "MEJ"}, f"tag-{token}-idem")
        assert replay["replayed"] is True
        metadata = db.query(LeadCrmMetadata).filter(LeadCrmMetadata.lead_id == lead_a.id).one()
        assert metadata.tags == ["MEJ"]

        db.refresh(lead_a)
        archive_payload = {"operation": "archive", "lead_ids": [str(lead_a.id)], "expected_updated_at": {str(lead_a.id): lead_a.updated_at.isoformat()}}
        assert bulk.execute(archive_payload, f"archive-{token}")["summary"]["accepted"] == 1
        db.refresh(metadata)
        assert metadata.archived_at is not None

        db.refresh(lead_a)
        stage_payload = {"operation": "negotiation_stage", "lead_ids": [str(lead_a.id)], "expected_updated_at": {str(lead_a.id): lead_a.updated_at.isoformat()}, "negotiation_stage": "RD"}
        assert bulk.execute(stage_payload, f"stage-{token}")["summary"]["accepted"] == 1

        db.refresh(lead_a)
        campaign_payload = {"operation": "campaign", "lead_ids": [str(lead_a.id)], "expected_updated_at": {str(lead_a.id): lead_a.updated_at.isoformat()}, "campaign_id": str(campaign.id)}
        assert bulk.execute(campaign_payload, f"campaign-{token}")["summary"]["accepted"] == 1
        db.refresh(lead_a)
        assert lead_a.campaign_id == campaign.id

        sequence_payload = {"operation": "start_sequence", "lead_ids": [str(lead_a.id)], "expected_updated_at": {str(lead_a.id): lead_a.updated_at.isoformat()}, "sequence_id": str(sequence.id)}
        assert bulk.execute(sequence_payload, f"sequence-{token}")["summary"]["accepted"] == 1
        enrollment = db.query(SequenceEnrollment).filter(SequenceEnrollment.lead_id == lead_a.id).one()
        assert enrollment.sequence_id == sequence.id
        assert db.query(SequenceExecution).filter(SequenceExecution.enrollment_id == enrollment.id).count() == 1

        assert db.query(CrmEntityAudit).filter(CrmEntityAudit.organization_id == org_a.id).count() >= 7
        assert db.query(LeadCrmMetadata).filter(LeadCrmMetadata.organization_id == org_b.id).count() == 0
        assert db.query(CrmEntityAudit).filter(CrmEntityAudit.organization_id == org_b.id).count() == 0
    finally:
        db.rollback()
        lead_ids = [lead_a.id, lead_b.id]
        db.query(SequenceExecution).filter(SequenceExecution.lead_id.in_(lead_ids)).delete(synchronize_session=False)
        db.query(SequenceEnrollment).filter(SequenceEnrollment.lead_id.in_(lead_ids)).delete(synchronize_session=False)
        db.query(LeadCrmMetadata).filter(LeadCrmMetadata.lead_id.in_(lead_ids)).delete(synchronize_session=False)
        db.query(CrmEntityAudit).filter(CrmEntityAudit.organization_id.in_([org_a.id, org_b.id])).delete(synchronize_session=False)
        db.query(CommercialBulkOperation).filter(CommercialBulkOperation.organization_id.in_([org_a.id, org_b.id])).delete(synchronize_session=False)
        db.query(Lead).filter(Lead.id.in_(lead_ids)).delete(synchronize_session=False)
        db.query(Person).filter(Person.id == person_a.id).delete(synchronize_session=False)
        db.query(SequenceTemplate).filter(SequenceTemplate.id == sequence.id).delete(synchronize_session=False)
        db.query(Campaign).filter(Campaign.id == campaign.id).delete(synchronize_session=False)
        db.query(Company).filter(Company.id.in_([company_a.id, company_b.id])).delete(synchronize_session=False)
        db.query(OrganizationMember).filter(OrganizationMember.organization_id == org_a.id).delete(synchronize_session=False)
        db.query(Organization).filter(Organization.id.in_([org_a.id, org_b.id])).delete(synchronize_session=False)
        db.query(User).filter(User.id == user.id).delete(synchronize_session=False)
        db.commit(); db.close()
