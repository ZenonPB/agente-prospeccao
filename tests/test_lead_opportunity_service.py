"""Testes do LeadOpportunityService (item 3 da auditoria de consolidacao).

Seam: `LeadOpportunityService.persist_opportunities(db, lead, opps)` e
`LeadOpportunityService.list_for_lead(db, lead_id)`.

Capacidade: persistir o resultado do OfferMatcher (1 lead -> N oportunidades)
em uma tabela propria (lead_opportunities), com upsert idempotente por
(lead_id, offer_key), preservando historico de score/evidencia. Endpoint
GET /api/leads/{id}/oportunidades expoe o resultado ao frontend.
"""
import os
import sys
import uuid
from pathlib import Path

# Workers no path (conftest ja faz, mas reforcamos para rodar este arquivo isolado).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Lead, Organization
from services.prospecting.offer_matcher import (
    LeadOpportunity,
    OfferMatcher,
)
from services.prospecting.default_profiles import get_default_registry

# Requer banco Postgres real (mesmo padrao do e2e_outreach_cycle.py).
# CI pula sem `E2E_DATABASE_URL`; se ausente mas `.env` define `DATABASE_URL`,
# usa esse (mesmo valor - ambiente local de dev).
import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOTENV = _REPO_ROOT / ".env"
if _DOTENV.exists():
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)

E2E_DB_URL = os.environ.get("E2E_DATABASE_URL") or os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not E2E_DB_URL,
    reason="E2E_DATABASE_URL/DATABASE_URL nao definido - testes de persistencia requerem Postgres",
)


@pytest.fixture()
def db_session():
    engine = create_engine(E2E_DB_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def sample_lead(db_session):
    org = Organization(
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Acme Test LeadOpp",
        slug=f"acme-test-leadoopp-{uuid.uuid4().hex[:8]}",
    )
    db_session.merge(org)
    db_session.flush()
    lead_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    db_session.query(Lead).filter(Lead.id == lead_id).delete()
    lead = Lead(
        id=lead_id,
        organization_id=org.id,
        company_name="Metalurgica Alpha",
        cnpj="12345678000199",
        city="Sao Paulo",
    )
    db_session.add(lead)
    db_session.flush()
    return lead


class TestLeadOpportunityService:
    """Seam: persistencia idempotente e leitura por lead."""

    def test_persist_creates_one_row_per_opportunity(self, db_session, sample_lead):
        from services.prospecting.lead_opportunity_service import (
            LeadOpportunityService,
        )

        opps = [
            LeadOpportunity(
                offer_key="mechanical_project",
                profile_key="industrial",
                score=80,
                evidence=["HAS_PHONE", "icp:cnae"],
                resolved_from="explicit",
                signals_matched=["HAS_PHONE"],
                signals_missing=[],
            ),
            LeadOpportunity(
                offer_key="technical_drawing",
                profile_key="industrial",
                score=70,
                evidence=["HAS_PHONE"],
                resolved_from="explicit",
                signals_matched=["HAS_PHONE"],
                signals_missing=[],
            ),
        ]

        service = LeadOpportunityService()
        service.persist_opportunities(db_session, sample_lead, opps)
        db_session.commit()

        rows = service.list_for_lead(db_session, sample_lead.id)
        assert len(rows) == 2
        keys = {r.offer_key for r in rows}
        assert keys == {"mechanical_project", "technical_drawing"}

    def test_persist_is_idempotent_on_rescore(self, db_session, sample_lead):
        """Re-rodar persist com scores novos substitui o anterior, sem duplicar."""
        from services.prospecting.lead_opportunity_service import (
            LeadOpportunityService,
        )

        service = LeadOpportunityService()
        first = [
            LeadOpportunity(
                offer_key="landing_page",
                profile_key="web_presence",
                score=50,
                evidence=["HAS_INSTAGRAM"],
                signals_matched=["HAS_INSTAGRAM"],
                signals_missing=["HAS_OWN_WEBSITE"],
            ),
        ]
        service.persist_opportunities(db_session, sample_lead, first)
        db_session.commit()

        second = [
            LeadOpportunity(
                offer_key="landing_page",
                profile_key="web_presence",
                score=85,
                evidence=["NO_OWN_WEBSITE", "HAS_INSTAGRAM", "HAS_PHONE"],
                resolved_from="explicit",
                signals_matched=["NO_OWN_WEBSITE", "HAS_INSTAGRAM", "HAS_PHONE"],
                signals_missing=[],
            ),
        ]
        service.persist_opportunities(db_session, sample_lead, second)
        db_session.commit()

        rows = service.list_for_lead(db_session, sample_lead.id)
        assert len(rows) == 1, "Upsert deve manter uma unica linha por offer_key"
        assert rows[0].score == 85
        assert "NO_OWN_WEBSITE" in rows[0].evidence

    def test_match_then_persist_round_trip(self, db_session, sample_lead):
        """Integracao completa: OfferMatcher.match -> persist -> list."""
        from services.prospecting.lead_opportunity_service import (
            LeadOpportunityService,
        )

        registry = get_default_registry()
        matcher = OfferMatcher(registry)
        opps = matcher.match(
            {
                "company_name": sample_lead.company_name,
                "cnae": "25",
                "has_cnpj": True,
                "has_phone": True,
                "has_own_website": True,
                "has_instagram": True,
            },
            min_score=1,
        )
        assert len(opps) >= 1, "Matcher devia achar pelo menos uma oportunidade industrial"

        service = LeadOpportunityService()
        service.persist_opportunities(db_session, sample_lead, opps)
        db_session.commit()

        rows = service.list_for_lead(db_session, sample_lead.id)
        assert len(rows) == len(opps)
        scores = [r.score for r in rows]
        assert scores == sorted(scores, reverse=True)