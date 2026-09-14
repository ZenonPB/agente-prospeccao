"""Gate formal do Bloco D.

D1 prova isolamento multi-workspace com UUIDs conhecidos.
D2 prova primitives de retry/cache/circuit-breaker e integridade operacional.
D3 ensaia release de campanhas e mede o funil usando entidades canônicas.
Nenhuma chamada externa é feita no CI.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import uuid

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_reachable import database_url, is_database_reachable

ROOT = Path(__file__).resolve().parent.parent
WORKERS = ROOT / "services" / "workers" / "src"
API = ROOT / "services" / "api"
for path in (str(API), str(WORKERS)):
    if path not in sys.path:
        sys.path.insert(0, path)
load_dotenv(ROOT / ".env", override=False)
DB_URL = database_url()


def test_production_resilience_is_bounded_tenant_scoped_and_redacted():
    from services.production_resilience import CircuitBreaker, RetryPolicy, redact_sensitive, tenant_cache_key

    org_a = uuid.uuid4(); org_b = uuid.uuid4()
    key_a = tenant_cache_key(org_a, "offer-registry", "landing_page", "2.0")
    key_b = tenant_cache_key(org_b, "offer-registry", "landing_page", "2.0")
    assert key_a != key_b
    assert str(org_a) in key_a and str(org_b) in key_b

    policy = RetryPolicy(max_attempts=4, base_seconds=1, cap_seconds=8, jitter_ratio=0)
    assert [policy.delay(i) for i in (1, 2, 3, 4)] == [1.0, 2.0, 4.0, 8.0]
    assert policy.delay(2, retry_after=99) == 8.0
    assert policy.should_retry(1, status_code=429) is True
    assert policy.should_retry(4, status_code=503) is False
    assert policy.should_retry(1, status_code=400) is False

    breaker = CircuitBreaker(failure_threshold=2, recovery_successes=2)
    breaker.record_failure(); assert breaker.state == "CLOSED"
    breaker.record_failure(); assert breaker.state == "OPEN" and breaker.allow() is False
    breaker.probe(); assert breaker.state == "HALF_OPEN" and breaker.allow() is True
    breaker.record_success(); assert breaker.state == "HALF_OPEN"
    breaker.record_success(); assert breaker.state == "CLOSED"

    raw = {"api_key": "secret", "Authorization": "Bearer x", "status": "ok"}
    safe = redact_sensitive(raw)
    assert safe["api_key"] == "***REDACTED***"
    assert safe["Authorization"] == "***REDACTED***"
    assert safe["status"] == "ok"
    assert raw["api_key"] == "secret"


def test_live_release_fails_closed_without_all_human_and_cost_guards():
    from src.services.block_d_service import CampaignReleaseRequest

    campaign_id = uuid.uuid4()
    with pytest.raises(ValueError, match="provider opt-in"):
        CampaignReleaseRequest(campaign_id, mode="LIVE_AUTHORIZED").validate()
    with pytest.raises(ValueError, match="autorização humana"):
        CampaignReleaseRequest(campaign_id, mode="LIVE_AUTHORIZED", provider_opt_in=True).validate()
    with pytest.raises(ValueError, match="justificativa"):
        CampaignReleaseRequest(
            campaign_id, mode="LIVE_AUTHORIZED", provider_opt_in=True, authorized_by=uuid.uuid4()
        ).validate()
    with pytest.raises(ValueError, match="teto de custo"):
        CampaignReleaseRequest(
            campaign_id, mode="LIVE_AUTHORIZED", provider_opt_in=True,
            authorized_by=uuid.uuid4(), authorization_note="campanha autorizada",
        ).validate()

    manifest = CampaignReleaseRequest(
        campaign_id, mode="LIVE_AUTHORIZED", provider_opt_in=True,
        authorized_by=uuid.uuid4(), authorization_note="30 contatos aprovados",
        cost_cap_brl=50, max_contacts=30,
    ).public_manifest()
    assert manifest["can_send_external"] is True


@pytest.mark.skipif(not is_database_reachable(DB_URL), reason="Postgres indisponível")
def test_d1_d2_d3_multi_workspace_rehearsal_and_measurement_postgres():
    from src.db.models import (
        Campaign, CommercialOutcomeRow, Lead, LeadOpportunityRow, LeadStatus,
        Organization, OrganizationMember, OrganizationRole, SalesRole, User,
    )
    from src.services.block_d_service import BlockDService, CampaignReleaseRequest
    from services.prospecting.effective_offer_registry import build_effective_registry

    engine = create_engine(DB_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    token = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc)

    org_a = Organization(name="AlphaMec UAT", slug=f"alphamec-uat-{token}")
    org_b = Organization(name="Vendas Samuel e Zenon UAT", slug=f"vendas-sz-uat-{token}")
    shared = User(email=f"block-d-{token}@example.com", password_hash="x", name="Shared User")
    db.add_all([org_a, org_b, shared]); db.flush()
    db.add_all([
        OrganizationMember(
            organization_id=org_a.id, user_id=shared.id,
            role=OrganizationRole.OWNER, sales_role=SalesRole.MANAGER,
        ),
        OrganizationMember(
            organization_id=org_b.id, user_id=shared.id,
            role=OrganizationRole.MEMBER, sales_role=SalesRole.CONSULTANT,
        ),
    ])
    db.flush()

    campaign_a = Campaign(
        user_id=shared.id, organization_id=org_a.id,
        name="AlphaMec — Landing Pages", target_service="landing pages",
        target_segment="clínicas", offer_profile_key="landing_page",
    )
    campaign_b = Campaign(
        user_id=shared.id, organization_id=org_b.id,
        name="Samuel e Zenon — mesmo nicho", target_service="landing pages",
        target_segment="clínicas", offer_profile_key="landing_page",
    )
    db.add_all([campaign_a, campaign_b]); db.flush()

    # Mesmo nome/segmento em workspaces distintos: identidade comercial não
    # pode ser colapsada pelo tenant switch.
    leads_a = []
    for index in range(4):
        lead = Lead(
            organization_id=org_a.id, campaign_id=campaign_a.id,
            company_name=f"Clínica Espelho {index}", city="Araraquara",
            category="psicologia", status=LeadStatus.QUALIFICADO,
            qualification_score=80 - index, assigned_to_id=shared.id,
            created_at=now, updated_at=now,
        )
        db.add(lead); db.flush(); leads_a.append(lead)
        opp = LeadOpportunityRow(
            organization_id=org_a.id, lead_id=lead.id, offer_key="landing_page",
            offer_version=build_effective_registry(db, org_a.id).get("landing_page").version,
            profile_key="web_presence", score=80 - index,
            signals_matched=["NO_OWN_WEBSITE"], signals_missing=["HAS_ADS"],
        )
        db.add(opp); db.flush()
        outcome = "WON" if index == 0 else "MEETING" if index == 1 else "REPLY"
        db.add(CommercialOutcomeRow(
            organization_id=org_a.id, lead_id=lead.id, lead_opportunity_id=opp.id,
            offer_key="landing_page", offer_version=opp.offer_version,
            outcome=outcome, value=1200 if outcome == "WON" else 0,
            event_key=f"block-d-a-{token}-{index}",
        ))

    foreign = Lead(
        organization_id=org_b.id, campaign_id=campaign_b.id,
        company_name="Clínica Espelho 0", city="Araraquara", category="psicologia",
        status=LeadStatus.QUALIFICADO, qualification_score=100,
        assigned_to_id=shared.id, created_at=now, updated_at=now,
    )
    db.add(foreign); db.flush()
    foreign_opp = LeadOpportunityRow(
        organization_id=org_b.id, lead_id=foreign.id, offer_key="landing_page",
        offer_version=build_effective_registry(db, org_b.id).get("landing_page").version,
        profile_key="web_presence", score=100, signals_matched=["NO_OWN_WEBSITE"],
    )
    db.add(foreign_opp); db.flush()
    db.add(CommercialOutcomeRow(
        organization_id=org_b.id, lead_id=foreign.id, lead_opportunity_id=foreign_opp.id,
        offer_key="landing_page", offer_version=foreign_opp.offer_version,
        outcome="WON", value=999999,
        event_key=f"block-d-b-{token}",
    ))
    db.flush()

    try:
        service_a = BlockDService(db, org_a.id)
        service_b = BlockDService(db, org_b.id)

        readiness = service_a.readiness()
        assert readiness["status"] == "READY"
        assert readiness["external_providers"] == "OPT_IN_REQUIRED"

        dry = service_a.release_manifest(CampaignReleaseRequest(campaign_a.id, mode="REHEARSAL"))
        assert dry["organization_id"] == str(org_a.id)
        assert dry["can_send_external"] is False
        assert dry["offer_key"] == "landing_page"

        live = service_a.release_manifest(CampaignReleaseRequest(
            campaign_a.id, mode="LIVE_AUTHORIZED", provider_opt_in=True,
            authorized_by=shared.id, authorization_note="Amostra controlada aprovada pelo gestor",
            cost_cap_brl=100, max_contacts=30,
        ))
        assert live["can_send_external"] is True

        with pytest.raises(ValueError, match="não encontrada neste workspace"):
            service_a.release_manifest(CampaignReleaseRequest(campaign_b.id, mode="DRY_RUN"))
        with pytest.raises(ValueError, match="não encontrada neste workspace"):
            service_a.campaign_funnel(campaign_b.id)

        funnel_a = service_a.campaign_funnel(campaign_a.id)
        funnel_b = service_b.campaign_funnel(campaign_b.id)
        assert funnel_a["leads"] == 4
        assert funnel_a["won"] == 1
        assert funnel_a["revenue"] == 1200.0
        assert funnel_a["attributed_outcomes"] == 4
        assert funnel_a["attribution_rate"] == 1.0
        assert funnel_b["leads"] == 1 and funnel_b["revenue"] == 999999.0
        assert funnel_a["revenue"] != funnel_b["revenue"]

        # Registry também precisa ser resolvido no tenant certo mesmo com o
        # mesmo usuário alternando workspaces.
        assert build_effective_registry(db, org_a.id).get("landing_page") is not None
        assert build_effective_registry(db, org_b.id).get("landing_page") is not None

        matrix = {row["offer_key"] for row in BlockDService.release_matrix()}
        assert {"landing_page", "web_systems_erp", "mechanical_engineering", "trophies_sports", "trophies_mej"} <= matrix
    finally:
        db.rollback()
        db.close()
