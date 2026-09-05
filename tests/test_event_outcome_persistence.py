"""Testes dos serviços persistentes de eventos e outcomes."""
import os
import uuid
from datetime import date
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, EventOpportunityRow, CommercialOutcomeRow, Lead, Organization

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)
DB_URL = os.environ.get("E2E_DATABASE_URL") or os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="Banco não configurado")


@pytest.fixture()
def session():
    engine = create_engine(DB_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    org = Organization(id=uuid.uuid4(), name="Persistencia Teste", slug=f"persist-{uuid.uuid4().hex[:8]}")
    db.add(org)
    db.flush()
    lead = Lead(id=uuid.uuid4(), organization_id=org.id, company_name="Empresa Teste", city="São Paulo")
    db.add(lead)
    db.commit()
    yield db, org, lead
    db.rollback()
    db.query(EventOpportunityRow).filter(EventOpportunityRow.organization_id == org.id).delete()
    db.query(CommercialOutcomeRow).filter(CommercialOutcomeRow.organization_id == org.id).delete()
    db.query(Lead).filter(Lead.id == lead.id).delete()
    db.query(Organization).filter(Organization.id == org.id).delete()
    db.commit()
    db.close()


def test_event_discovery_persists_idempotently(session):
    from services.prospecting.event_opportunity_service import EventOpportunityService

    db, org, _lead = session
    service = EventOpportunityService()
    event = {
        "name": "Copa Alpha",
        "event_type": "sport",
        "event_date": "2030-06-15",
        "location": "São Paulo",
        "source_url": "https://events.example/copa-alpha",
        "organizer": "cbk",
        "organizer_resolved": {"source": "exact"},
        "timing": {"timing_score": 100},
    }
    first = service.replace_events(db, org.id, [event])
    second = service.replace_events(db, org.id, [event])
    db.commit()
    rows = service.list_for_organization(db, org.id)
    assert len(first) == 1
    assert len(second) == 1
    assert len(rows) == 1
    assert rows[0].event_date == date(2030, 6, 15)


def test_commercial_outcome_is_idempotent_and_metrics_are_real(session):
    from services.prospecting.commercial_outcome_service import CommercialOutcomeService

    db, org, lead = session
    service = CommercialOutcomeService()
    first = service.record_for_lead(db, org.id, lead.id, "WON", "conversion:lead-1", value=1500)
    same = service.record_for_lead(db, org.id, lead.id, "WON", "conversion:lead-1", value=999)
    second = service.record_for_lead(db, org.id, lead.id, "LOST", "status:lead-1:lost")
    db.commit()
    rows = service.list_for_organization(db, org.id)
    metrics = service.metrics(rows)
    assert first.id == same.id
    assert second.id != first.id
    assert len(rows) == 2
    assert metrics["metrics"][0]["total"] == 2
    assert metrics["metrics"][0]["won"] == 1
    assert metrics["metrics"][0]["conversion_rate"] == 50.0