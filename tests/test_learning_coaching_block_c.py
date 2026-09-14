"""Gate formal do Bloco C: replay, learning human-in-loop, publicação e coaching."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


def test_learning_proposal_preserves_persisted_candidate_snapshot():
    from types import SimpleNamespace
    from src.services.controlled_learning_service import build_learning_proposal

    candidate = {"key": "landing_page", "version": "1.1"}
    comparison = SimpleNamespace(
        id=uuid.uuid4(), organization_id=uuid.uuid4(), offer_key="landing_page",
        version_a="1.0", version_b="1.1", approved_version="1.1",
        approved_by_id=uuid.uuid4(),
        result={
            "verdict": "v2", "recommendation": "candidato venceu", "delta": {},
            "v1": {}, "v2": {}, "candidate_profile_snapshot": candidate,
            "sample_quality": {"eligible_for_proposal": True},
        },
    )
    payload = build_learning_proposal(comparison)
    assert payload["evidence_snapshot"]["candidate_profile_snapshot"] == candidate
    assert payload["requires_manual_publication"] is True


def _next_minor(version: str) -> str:
    major, minor = version.split(".", 1)
    return f"{int(major)}.{int(minor) + 1}"


@pytest.mark.skipif(not is_database_reachable(DB_URL), reason="Postgres indisponível")
def test_block_c_replay_publish_rollback_coaching_and_tenant_isolation_postgres():
    from database.learning_models import OfferProfileActivation, OfferProfileVersion
    from src.db.models import (
        CommercialComparison, CommercialOutcomeRow, ControlledLearningProposal,
        Lead, LeadOpportunityRow, LeadStatus, Organization, OrganizationMember,
        OrganizationRole, SalesRole, User,
    )
    from src.services.commercial_comparison_service import CommercialComparisonService
    from src.services.controlled_learning_service import ControlledLearningService
    from src.services.learning_coaching_service import CommercialCoachingService, LearningCalibrationService
    from services.prospecting.effective_offer_registry import build_effective_registry

    engine = create_engine(DB_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    token = uuid.uuid4().hex[:8]
    org_a = Organization(name="Bloco C A", slug=f"block-c-a-{token}")
    org_b = Organization(name="Bloco C B", slug=f"block-c-b-{token}")
    manager = User(email=f"block-c-{token}@example.com", password_hash="x", name="Gestor C")
    db.add_all([org_a, org_b, manager]); db.flush()
    db.add(OrganizationMember(
        organization_id=org_a.id, user_id=manager.id,
        role=OrganizationRole.OWNER, sales_role=SalesRole.MANAGER,
    ))
    db.flush()

    now = datetime.now(timezone.utc)
    baseline = build_effective_registry(db, org_a.id).get("landing_page")
    foreign_baseline = build_effective_registry(db, org_b.id).get("landing_page")
    assert baseline is not None and foreign_baseline is not None
    baseline_version = baseline.version
    candidate_version = _next_minor(baseline_version)

    for index in range(12):
        signal_a = index < 6
        # O grupo A tem o sinal que de fato concentra reuniões/vendas. O grupo
        # B começa acima no ranking porque combina ICP + sinais opcionais. A
        # calibração conservadora precisa inverter essa ordenação sem fabricar
        # FALSE para sinais ausentes.
        opp_id = uuid.UUID(int=(index + 1) if signal_a else ((1 << 128) - (index + 1)))
        lead = Lead(
            organization_id=org_a.id,
            company_name=f"Empresa C {index}", city="Araraquara",
            category=None if signal_a else "psicologia",
            status=LeadStatus.QUALIFICADO, qualification_score=70,
            assigned_to_id=manager.id,
            next_action_at=now - timedelta(days=1) if index < 3 else now + timedelta(days=3),
            created_at=now - timedelta(days=2), updated_at=now - timedelta(days=1),
        )
        db.add(lead); db.flush()
        matched = ["NO_OWN_WEBSITE"] if signal_a else [
            "HAS_INSTAGRAM", "HAS_ADS", "WEAK_CTA", "NO_CONTACT_FORM", "WEAK_CONVERSION_FLOW",
        ]
        opportunity = LeadOpportunityRow(
            id=opp_id, organization_id=org_a.id, lead_id=lead.id,
            offer_key="landing_page", offer_version=baseline_version, profile_key="web_presence",
            score=35,
            signals_matched=matched,
            signals_missing=["HAS_INSTAGRAM"] if signal_a else ["NO_OWN_WEBSITE"],
        )
        db.add(opportunity); db.flush()
        outcome = "WON" if signal_a and index < 3 else "MEETING" if signal_a else "REPLY"
        db.add(CommercialOutcomeRow(
            organization_id=org_a.id, lead_id=lead.id,
            lead_opportunity_id=opportunity.id, offer_key="landing_page",
            offer_version=baseline_version, outcome=outcome,
            value=1000 if outcome == "WON" else 0,
            event_key=f"block-c-{token}-{index}",
        ))

    # Ruído do outro tenant: precisa permanecer invisível para A.
    foreign_lead = Lead(
        organization_id=org_b.id, company_name="Empresa estrangeira", city="São Carlos",
        status=LeadStatus.QUALIFICADO, qualification_score=100, created_at=now, updated_at=now,
    )
    db.add(foreign_lead); db.flush()
    foreign_opp = LeadOpportunityRow(
        organization_id=org_b.id, lead_id=foreign_lead.id,
        offer_key="landing_page", offer_version="9.9", profile_key="web_presence",
        score=100, signals_matched=["HAS_INSTAGRAM"],
    )
    db.add(foreign_opp); db.flush()
    db.add(CommercialOutcomeRow(
        organization_id=org_b.id, lead_id=foreign_lead.id,
        lead_opportunity_id=foreign_opp.id, offer_key="landing_page",
        offer_version="9.9", outcome="WON", value=999999,
        event_key=f"block-c-foreign-{token}",
    ))
    db.flush()

    try:
        calibration = LearningCalibrationService(db, org_a.id)
        report = calibration.calibration_report("landing_page", min_samples=12)
        assert report["active_version"] == baseline_version
        assert report["sample_quality"]["eligible_for_proposal"] is True
        assert report["sample_quality"]["observed_opportunities"] == 12
        assert report["sample_quality"]["wins"] == 3
        assert report["sample_quality"]["attribution_rate"] == 1.0

        suggested = calibration.suggested_candidate("landing_page", min_samples=12)
        candidate = suggested["profile_snapshot"]
        assert candidate["version"] == candidate_version
        assert suggested["changes"]
        replay = calibration.replay("landing_page", candidate, min_samples=12, top_k=6)
        assert replay["verdict"] == "v2"
        assert replay["version_a"] == baseline_version
        assert replay["version_b"] == candidate_version
        assert replay["v2"]["win_precision"] > replay["v1"]["win_precision"]
        assert replay["methodology"]["unknown_semantics"].startswith("sinal ausente")

        comparison = calibration.create_calibration_comparison(
            "landing_page", candidate, min_samples=12, top_k=6,
        )
        assert isinstance(comparison, CommercialComparison)
        approved = CommercialComparisonService().approve(
            db, org_a.id, comparison.id, comparison.version_b, manager,
            "Replay histórico atribuído validado no gate do Bloco C.",
        )
        assert approved.approved_version == candidate_version

        learning = ControlledLearningService()
        proposal = learning.create_from_comparison(db, org_a.id, comparison.id, manager)
        assert proposal.status == "PROPOSED"
        assert proposal.evidence_snapshot["candidate_profile_snapshot"]["version"] == candidate_version

        published = learning.publish_profile(db, org_a.id, proposal.id, None, manager)
        assert published.version == candidate_version
        assert published.is_active is True
        effective = build_effective_registry(db, org_a.id).get("landing_page")
        foreign_effective = build_effective_registry(db, org_b.id).get("landing_page")
        assert effective is not None and effective.version == candidate_version
        assert foreign_effective is not None and foreign_effective.version == foreign_baseline.version

        rolled = learning.rollback_profile(db, org_a.id, "landing_page", baseline_version, manager)
        assert rolled.version == baseline_version and rolled.is_active is True
        assert build_effective_registry(db, org_a.id).get("landing_page").version == baseline_version

        coaching = CommercialCoachingService(db, org_a.id).dashboard()
        assert coaching["team"]["assigned_leads"] == 12
        assert coaching["team"]["overdue_followups"] == 3
        assert coaching["consultants"][0]["user_id"] == str(manager.id)
        kinds = {item["kind"] for item in coaching["consultants"][0]["recommendations"]}
        assert "FOLLOW_UP_SLA" in kinds
        assert all(item["association_not_causation"] for item in coaching["consultants"][0]["recommendations"])

        assert db.query(ControlledLearningProposal).filter(ControlledLearningProposal.organization_id == org_a.id).count() == 1
        assert db.query(OfferProfileVersion).filter(OfferProfileVersion.organization_id == org_b.id).count() == 0
        assert db.query(OfferProfileActivation).filter(OfferProfileActivation.organization_id == org_b.id).count() == 0
    finally:
        db.rollback()
        db.close()
