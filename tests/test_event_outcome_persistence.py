"""Testes dos serviços persistentes de eventos, Golden Paths e outcomes."""
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_reachable import database_url, is_database_reachable
from database.models import Contact, EventOpportunityRow, CommercialOutcomeRow, Lead, LeadOpportunityRow, Organization

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)
DB_URL = database_url()
pytestmark = pytest.mark.skipif(
    not is_database_reachable(DB_URL),
    reason="Postgres indisponivel - testes de persistencia requerem banco real",
)


def future_iso(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


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
    db.query(LeadOpportunityRow).filter(LeadOpportunityRow.organization_id == org.id).delete()
    db.query(CommercialOutcomeRow).filter(CommercialOutcomeRow.organization_id == org.id).delete()
    db.query(Contact).filter(Contact.lead_id == lead.id).delete()
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
        "event_date": future_iso(45),
        "location": "São Paulo",
        "source_url": "https://events.example/copa-alpha",
        "organizer": "cbk",
        "organizer_resolved": {"source": "exact"},
    }
    first = service.replace_events(db, org.id, [event])
    second = service.replace_events(db, org.id, [event])
    db.commit()
    rows = service.list_for_organization(db, org.id)
    assert len(first) == 1
    assert len(second) == 1
    assert len(rows) == 1
    assert rows[0].event_date == date.today() + timedelta(days=45)
    assert rows[0].offer_key == "trophies_sports"
    assert rows[0].provenance["intelligence"]["context"] == "sports"
    assert rows[0].provenance["intelligence"]["demand"]["epistemic"] == "INFERENCE"


def test_evento_esportivo_gera_oportunidade_especifica_idempotente(session):
    from services.prospecting.default_profiles import get_default_registry
    from services.prospecting.event_opportunity_service import EventOpportunityService

    db, org, lead = session
    lead.company_name = "Empresa Esportiva Alpha"
    lead.name = lead.company_name
    lead.category = "campeonatos"
    lead.phone = "+5511999999999"
    db.flush()
    event = {
        "name": "Copa Alpha",
        "event_type": "sport",
        "event_date": future_iso(45),
        "location": "São Paulo",
        "source_url": "https://events.example/copa-alpha-opportunity",
        "organizer": "Empresa Esportiva Alpha",
        "organizer_resolved": {
            "official_name": "Empresa Esportiva Alpha",
            "confidence": 0.95,
        },
    }

    service = EventOpportunityService()
    rows = service.replace_events(db, org.id, [event])
    assert rows[0].status == "upcoming"
    assert rows[0].lead_id == lead.id
    assert rows[0].offer_key == "trophies_sports"
    first = service.match_event_opportunities(db, rows)
    second = service.match_event_opportunities(db, rows)
    db.commit()

    assert first["matched"] == 1, first
    assert second["matched"] == 1
    opportunities = db.query(LeadOpportunityRow).filter(
        LeadOpportunityRow.lead_id == lead.id,
        LeadOpportunityRow.offer_key == "trophies_sports",
    ).all()
    assert len(opportunities) == 1
    expected_version = get_default_registry().get("trophies_sports").version
    assert opportunities[0].offer_version == expected_version
    assert "EVENT_SCHEDULED" in opportunities[0].evidence
    assert "EVENT_CONTEXT_SPORTS" in opportunities[0].evidence


def test_evento_mej_persiste_contexto_timing_e_oportunidade_sem_inventar_fato(session):
    """Golden Path MEJ completo: evento -> contexto -> lead -> oportunidade."""
    from services.prospecting.event_opportunity_service import EventOpportunityService

    db, org, lead = session
    organizer = "Núcleo Exemplo de Empresas Juniores"
    lead.company_name = organizer
    lead.name = organizer
    lead.category = "MEJ"
    lead.phone = "+5516999999999"
    db.flush()

    event = {
        "name": "ENEJ 2030 - Encontro de Empresas Juniores",
        "event_type": "evento universitário",
        "event_date": future_iso(50),
        "location": "São Paulo, SP",
        "source_url": "https://events.example/enej-2030",
        "organizer": organizer,
        "organizer_resolved": {"official_name": organizer, "confidence": 0.96},
        "category_count": 8,
        "placements_per_category": 3,
    }

    service = EventOpportunityService()
    rows = service.replace_events(db, org.id, [event])
    assert len(rows) == 1
    row = rows[0]
    intelligence = row.provenance["intelligence"]
    assert row.lead_id == lead.id
    assert row.offer_key == "trophies_mej"
    assert intelligence["context"] == "mej"
    assert intelligence["demand"]["epistemic"] == "INFERENCE"
    assert intelligence["demand"]["estimated_min_units"] == 24
    assert row.timing["purchase_window"] == "ideal"
    assert row.timing["timing_score"] >= 88

    first = service.match_event_opportunities(db, rows)
    second = service.match_event_opportunities(db, rows)
    db.commit()

    assert first["matched"] == 1, first
    assert second["matched"] == 1
    opportunities = db.query(LeadOpportunityRow).filter(
        LeadOpportunityRow.lead_id == lead.id,
        LeadOpportunityRow.offer_key == "trophies_mej",
    ).all()
    assert len(opportunities) == 1
    assert "EVENT_SCHEDULED" in opportunities[0].evidence
    assert "EVENT_CONTEXT_MEJ" in opportunities[0].evidence
    assert "CONTACT_WINDOW_GOOD" in opportunities[0].evidence


def test_evento_com_contato_persistido_gera_acao_comercial_sem_enviar_mensagem(session):
    from database.models import ContactRole
    from services.prospecting.event_opportunity_service import EventOpportunityService

    db, org, lead = session
    lead.company_name = "Empresa Esportiva Alpha"
    lead.name = lead.company_name
    lead.category = "campeonatos"
    contact = Contact(
        lead_id=lead.id,
        name="Maria Organizadora",
        role=ContactRole.ADMINISTRADOR,
        phone="16999998888",
        confidence=90,
        is_primary=True,
        source="company_site",
    )
    db.add(contact)
    db.flush()
    event = {
        "name": "Copa Alpha Ação",
        "event_type": "sport",
        "event_date": future_iso(45),
        "location": "São Paulo",
        "source_url": "https://events.example/copa-alpha-action",
        "organizer": "Empresa Esportiva Alpha",
        "organizer_resolved": {"official_name": "Empresa Esportiva Alpha", "confidence": 0.95},
    }

    service = EventOpportunityService()
    rows = service.replace_events(db, org.id, [event])
    service.match_event_opportunities(db, rows)
    action_result = service.prepare_event_actions(db, rows)
    db.commit()
    db.refresh(rows[0])

    assert action_result == {"ready": 1, "needs_review": 0, "not_found": 0, "errors": []}
    assert rows[0].decision_maker_id == contact.id
    assert rows[0].decision_maker_status == "resolved"
    assert rows[0].recommended_channel == "phone"
    assert rows[0].action_status == "ready"
    assert "não enviar" in rows[0].next_action.lower()


def test_timing_calculado_entra_na_acao_persistida(session):
    from services.prospecting.event_opportunity_service import EventOpportunityService

    db, org, lead = session
    lead.company_name = "Organizador Timing"
    lead.name = lead.company_name
    contact = Contact(
        lead_id=lead.id,
        name="Carlos Timing",
        phone="16999998888",
        confidence=90,
        is_primary=True,
        source="company_site",
    )
    db.add(contact)
    db.flush()
    event = {
        "name": "Copa Timing",
        "event_type": "sport",
        "event_date": future_iso(45),
        "location": "São Paulo",
        "source_url": "https://events.example/copa-timing",
        "organizer": lead.company_name,
        "organizer_resolved": {"official_name": lead.company_name, "confidence": 0.95},
    }

    service = EventOpportunityService()
    rows = service.replace_events(db, org.id, [event])
    service.match_event_opportunities(db, rows)
    service.prepare_event_actions(db, rows)
    db.commit()
    db.refresh(rows[0])

    assert rows[0].action_status == "ready"
    assert rows[0].timing["purchase_window"] == "ideal"
    assert "45" in (rows[0].next_action or "")
    assert "janela ideal" in (rows[0].next_action or "").lower()


def test_snapshot_de_resolucao_e_append_only_e_idempotente(session):
    from database.models import DecisionResolutionSnapshot
    from services.prospecting.resolution_snapshot_service import ResolutionSnapshotService

    db, org, lead = session
    service = ResolutionSnapshotService()
    first = service.persist(db, org.id, lead.id, "resolved", {"people": [{"name": "Ana", "email": "ana@example.com"}]})
    same = service.persist(db, org.id, lead.id, "resolved", {"people": [{"email": "ana@example.com", "name": "Ana"}]})
    changed = service.persist(db, org.id, lead.id, "partial", {"people": [{"name": "Ana"}]})
    db.commit()

    rows = db.query(DecisionResolutionSnapshot).filter(DecisionResolutionSnapshot.lead_id == lead.id).all()
    assert same.id == first.id
    assert changed.id != first.id
    assert len(rows) == 2
    assert {row.status for row in rows} == {"resolved", "partial"}


def test_confianças_do_contato_sao_persistidas_no_postgresql(session):
    from services.contact_enrichment_service import ContactEnrichmentService

    db, _org, lead = session
    contact = Contact(
        lead_id=lead.id,
        name="Maria Silva",
        email="maria@empresa.com.br",
        email_verified=True,
        email_verified_at=datetime.now(timezone.utc),
        linkedin_url="https://www.linkedin.com/in/maria-silva",
        source="company_site",
        raw_data={"email_source": "verified_email", "linkedin_source": "linkedin_current"},
    )
    db.add(contact)
    db.flush()
    ContactEnrichmentService().update_contact_confidence(contact)
    db.commit()
    db.expire_all()

    persisted = db.query(Contact).filter(Contact.id == contact.id).one()
    assert persisted.identity_confidence >= 70
    assert persisted.contact_confidence >= 80
    assert persisted.source_reliability == 0.9
    assert persisted.verification_status == "fully_verified"
    assert persisted.last_verified_at is not None


def test_routability_do_contato_e_persistida_no_postgresql(session):
    from services.contact_enrichment_service import ContactEnrichmentService

    db, _org, lead = session
    contact = Contact(lead_id=lead.id, name="Maria Silva", phone="1633334000", source="company_site")
    db.add(contact)
    db.flush()
    ContactEnrichmentService().update_contact_confidence(contact)
    db.commit()
    db.expire_all()

    persisted = db.query(Contact).filter(Contact.id == contact.id).one()
    assert persisted.routability_type == "DIRECT_CONTACT"
    assert persisted.routable is True
    assert persisted.routability_reason == "direct_line"


def test_provenance_de_discovery_e_persistida_no_lead(session):
    db, _org, lead = session
    lead.discovery_provenance = {
        "provider": "google_places",
        "provider_query": "metalúrgica São Paulo",
        "provider_candidate_id": "place-1",
        "retrieved_at": "2030-01-01T12:00:00+00:00",
        "discovery_plan_id": "mechanical_engineering",
        "matched_identity_rule": "normalized_domain",
        "identity_status": "confirmed",
        "identity_confidence": 0.95,
        "providers": ["google_places", "cnae_discovery"],
    }
    db.commit()
    db.expire_all()
    persisted = db.query(Lead).filter(Lead.id == lead.id).one()
    assert persisted.discovery_provenance["providers"] == ["google_places", "cnae_discovery"]
    assert persisted.discovery_provenance["matched_identity_rule"] == "normalized_domain"


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
    assert metrics["metrics"][0]["sample_size"] == 2
    assert metrics["metrics"][0]["sample_minimum"] == 5
    assert metrics["metrics"][0]["sample_sufficient"] is False


def test_commercial_outcomes_filtra_periodo_inclusivo(session):
    from services.prospecting.commercial_outcome_service import CommercialOutcomeService

    db, org, lead = session
    service = CommercialOutcomeService()
    old = service.record_for_lead(db, org.id, lead.id, "LOST", "old", offer_key="landing_page")
    old.recorded_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    current = service.record_for_lead(db, org.id, lead.id, "WON", "current", offer_key="landing_page")
    current.recorded_at = datetime(2025, 2, 1, tzinfo=timezone.utc)
    db.commit()

    rows = service.list_for_organization(
        db, org.id, offer_key="landing_page",
        date_from=date(2025, 2, 1), date_to=date(2025, 2, 1),
    )
    assert [row.event_key for row in rows] == ["current"]
