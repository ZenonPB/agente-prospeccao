"""Histórico de oportunidades e política de re-scoring.

Seams:
- `build_snapshot_hash` (hash canônico idempotente).
- `should_apply_rescore` (política explícita de versão).
- `LeadOpportunityService.persist/replace/list_snapshots` (Postgres real).
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_reachable import database_url, is_database_reachable
from database.models import Base, Lead, Organization


class TestSnapshotHash:
    def test_hash_estavel_para_mesma_avaliacao(self):
        from services.prospecting.lead_opportunity_service import build_snapshot_hash

        first = build_snapshot_hash("trophies", "1.0", 80, ["A"], ["A"], [])
        second = build_snapshot_hash("trophies", "1.0", 80, ["A"], ["A"], [])
        assert first == second
        assert len(first) == 64

    def test_hash_muda_com_versao_ou_score(self):
        from services.prospecting.lead_opportunity_service import build_snapshot_hash

        base = build_snapshot_hash("trophies", "1.0", 80, ["A"], ["A"], [])
        other_version = build_snapshot_hash("trophies", "1.1", 80, ["A"], ["A"], [])
        other_score = build_snapshot_hash("trophies", "1.0", 81, ["A"], ["A"], [])
        assert base != other_version
        assert base != other_score


class TestRescorePolicy:
    def test_mesma_versao_atualiza(self):
        from services.prospecting.lead_opportunity_service import should_apply_rescore

        assert should_apply_rescore("1.0", "1.0") is True
        assert should_apply_rescore(None, None) is True

    def test_versao_nova_sem_reanalyze_preserva(self):
        from services.prospecting.lead_opportunity_service import should_apply_rescore

        assert should_apply_rescore("1.0", "1.1", explicit_reanalyze=False) is False

    def test_versao_nova_com_reanalyze_aplica(self):
        from services.prospecting.lead_opportunity_service import should_apply_rescore

        assert should_apply_rescore("1.0", "1.1", explicit_reanalyze=True) is True


DB_URL = database_url()
_persistencia = pytest.mark.skipif(
    not is_database_reachable(DB_URL),
    reason="Postgres indisponivel - testes de persistencia requerem banco real",
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


@pytest.fixture()
def sample_lead(db_session):
    org = Organization(
        id=uuid.UUID("00000000-0000-0000-0000-000000000011"),
        name="Acme Historico",
        slug=f"acme-historico-{uuid.uuid4().hex[:8]}",
    )
    db_session.merge(org)
    db_session.flush()
    lead = Lead(
        id=uuid.uuid4(),
        organization_id=org.id,
        company_name="Metalurgica Historica",
        city="Sao Paulo",
    )
    db_session.add(lead)
    db_session.flush()
    return lead


@_persistencia
class TestOpportunityHistory:
    def test_persist_gera_snapshot(self, db_session, sample_lead):
        from services.prospecting.lead_opportunity_service import LeadOpportunityService
        from services.prospecting.offer_matcher import LeadOpportunity

        service = LeadOpportunityService()
        service.persist_opportunities(
            db_session, sample_lead,
            [LeadOpportunity(offer_key="trophies", profile_key="x", score=70,
                             offer_version="1.0", evidence=["A"],
                             signals_matched=["A"], signals_missing=[])],
        )
        db_session.commit()
        snaps = service.list_snapshots(db_session, sample_lead.id)
        assert len(snaps) == 1
        assert snaps[0].offer_version == "1.0"
        assert snaps[0].snapshot_hash

    def test_troca_de_versao_preserva_sem_reanalyze(self, db_session, sample_lead):
        from services.prospecting.lead_opportunity_service import LeadOpportunityService
        from services.prospecting.offer_matcher import LeadOpportunity

        service = LeadOpportunityService()
        service.persist_opportunities(
            db_session, sample_lead,
            [LeadOpportunity(offer_key="trophies", profile_key="x", score=70,
                             offer_version="1.0", evidence=["A"],
                             signals_matched=["A"], signals_missing=[])],
        )
        db_session.commit()
        service.persist_opportunities(
            db_session, sample_lead,
            [LeadOpportunity(offer_key="trophies", profile_key="x", score=90,
                             offer_version="1.1", evidence=["B"],
                             signals_matched=["B"], signals_missing=[])],
        )
        db_session.commit()
        rows = service.list_for_lead(db_session, sample_lead.id)
        assert rows[0].offer_version == "1.0"
        assert rows[0].score == 70

    def test_reanalyze_explicito_aplica_nova_versao(self, db_session, sample_lead):
        from services.prospecting.lead_opportunity_service import LeadOpportunityService
        from services.prospecting.offer_matcher import LeadOpportunity

        service = LeadOpportunityService()
        service.persist_opportunities(
            db_session, sample_lead,
            [LeadOpportunity(offer_key="trophies", profile_key="x", score=70,
                             offer_version="1.0", evidence=["A"],
                             signals_matched=["A"], signals_missing=[])],
        )
        db_session.commit()
        service.persist_opportunities(
            db_session, sample_lead,
            [LeadOpportunity(offer_key="trophies", profile_key="x", score=90,
                             offer_version="1.1", evidence=["B"],
                             signals_matched=["B"], signals_missing=[])],
            reason="reanalyze", explicit_reanalyze=True,
        )
        db_session.commit()
        rows = service.list_for_lead(db_session, sample_lead.id)
        assert rows[0].offer_version == "1.1"
        assert rows[0].score == 90
        snaps = service.list_snapshots(db_session, sample_lead.id)
        assert len(snaps) >= 2

    def test_replace_preserva_removida_no_historico(self, db_session, sample_lead):
        from services.prospecting.lead_opportunity_service import LeadOpportunityService
        from services.prospecting.offer_matcher import LeadOpportunity

        service = LeadOpportunityService()
        service.persist_opportunities(
            db_session, sample_lead,
            [LeadOpportunity(offer_key="trophies", profile_key="x", score=70,
                             offer_version="1.0", evidence=["A"],
                             signals_matched=["A"], signals_missing=[])],
        )
        db_session.commit()
        service.replace_opportunities(db_session, sample_lead, [], reason="enrichment")
        db_session.commit()
        assert service.list_for_lead(db_session, sample_lead.id) == []
        snaps = service.list_snapshots(db_session, sample_lead.id)
        assert any(s.offer_key == "trophies" for s in snaps)
