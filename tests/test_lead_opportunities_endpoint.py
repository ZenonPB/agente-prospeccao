"""Testes do endpoint GET /api/leads/{id}/oportunidades (item 3).

Seam: rota FastAPI GET /leads/{lead_id}/oportunidades -> LeadOpportunityService.
Capacidade: expor as oportunidades persistidas via LeadOpportunityRow para o
frontend. Valida contrato do response, ordem (score desc) e 200 com lista
vazia quando o lead nao tem oportunidades.
"""
import os
import sys
import uuid
from pathlib import Path

# Carrega .env primeiro (mesmo padrao de test_lead_opportunity_service).
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DOTENV = _REPO_ROOT / ".env"
if _DOTENV.exists():
    from dotenv import load_dotenv

    load_dotenv(_DOTENV, override=False)

sys.path.insert(0, str(_REPO_ROOT / "services" / "workers" / "src"))

# API primeiro; senao `main` pode resolver para workers/src/main.py.
# Importante: como `sys.path.insert(0, ...)` empurra para o inicio,
# garantir que `services/api` esteja antes de `services/workers/src` no inicio.
import sys as _sys

_API = str(_REPO_ROOT / "services" / "api")
_WORKERS = str(_REPO_ROOT / "services" / "workers" / "src")
_sys.path = [p for p in _sys.path if p not in (_API, _WORKERS)]
_sys.path.insert(0, _API)
_sys.path.insert(1, _WORKERS)

import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from database.models import Base, Lead, LeadOpportunityRow, Organization  # noqa: E402

# Mesma regra de skip do test_lead_opportunity_service: precisa de Postgres.
DB_URL = os.environ.get("E2E_DATABASE_URL") or os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DB_URL,
    reason="E2E_DATABASE_URL/DATABASE_URL nao definido",
)


@pytest.fixture()
def engine():
    eng = create_engine(DB_URL)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine)
@pytest.fixture()
def seeded(session_factory):
    """Cria org + lead + 2 oportunidades para teste."""
    Session = session_factory
    session = Session()
    try:
        org_id = uuid.uuid4()
        lead_id = uuid.uuid4()
        org = Organization(
            id=org_id,
            name="Acme Endpoint",
            slug=f"acme-endpoint-{uuid.uuid4().hex[:8]}",
        )
        session.merge(org)
        session.flush()
        session.query(LeadOpportunityRow).filter(LeadOpportunityRow.lead_id == lead_id).delete()
        session.query(Lead).filter(Lead.id == lead_id).delete()
        lead = Lead(
            id=lead_id,
            organization_id=org.id,
            company_name="Clinica XYZ",
            cnpj="98765432000111",
            city="Curitiba",
        )
        session.add(lead)
        session.flush()
        for off_key, score in [
            ("landing_page", 88),
            ("mechanical_project", 72),
        ]:
            row = LeadOpportunityRow(
                lead_id=lead.id,
                organization_id=org.id,
                offer_key=off_key,
                profile_key="industrial",
                score=score,
                resolved_from="explicit",
                evidence=[f"SIGNAL_FOR_{off_key}"],
                signals_matched=[f"SIGNAL_FOR_{off_key}"],
                signals_missing=[],
            )
            session.add(row)
        session.commit()
        return {"org_id": org.id, "lead_id": lead.id}
    finally:
        session.close()


def _client_with_stubs(org_id):
    """Cria TestClient com overrides de get_db/get_current_user/get_user_organization."""
    os.environ["DATABASE_URL"] = DB_URL
    from fastapi.testclient import TestClient

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "prospect_api_main", _REPO_ROOT / "services" / "api" / "main.py",
    )
    api_main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api_main)
    app = api_main.app
    from src.db.dependencies import get_db
    from src.auth.dependencies import get_current_user, get_user_organization, get_user_membership
    from src.db.models import OrganizationMember, OrganizationRole, SalesRole

    SessionLocal = sessionmaker(bind=create_engine(DB_URL))

    def _override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    user_id = uuid.UUID("00000000-0000-0000-0000-000000000099")

    class _StubUser:
        def __init__(self, uid, oid):
            self.id = uid
            self.organization_id = oid
            self.email = "stub@test.local"

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: _StubUser(user_id, org_id)
    app.dependency_overrides[get_user_organization] = lambda: Organization(
        id=org_id, name="Acme Stub", slug=f"acme-stub-{uuid.uuid4().hex[:8]}",
    )
    app.dependency_overrides[get_user_membership] = lambda: OrganizationMember(
        user_id=user_id, organization_id=org_id,
        role=OrganizationRole.MEMBER, sales_role=SalesRole.CONSULTOR,
    )
    return TestClient(app), app


def test_endpoint_returns_opportunities_in_score_order(seeded):
    """GET /api/leads/{id}/oportunidades retorna lista ordenada por score desc."""
    client, app = _client_with_stubs(seeded["org_id"])
    try:
        resp = client.get(f"/api/leads/{seeded['lead_id']}/oportunidades")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "oportunidades" in body
        opps = body["oportunidades"]
        assert len(opps) == 2
        scores = [o["score"] for o in opps]
        assert scores == sorted(scores, reverse=True)
        assert opps[0]["offer_key"] == "landing_page"
        assert opps[1]["offer_key"] == "mechanical_project"
    finally:
        app.dependency_overrides.clear()


def test_endpoint_returns_empty_when_lead_has_no_opportunities(session_factory):
    """Lead sem oportunidades -> 200 com lista vazia."""
    Session = session_factory
    session = Session()
    try:
        org = Organization(
            id=uuid.uuid4(),
            name="Acme Empty",
            slug=f"acme-empty-{uuid.uuid4().hex[:8]}",
        )
        session.merge(org)
        session.flush()
        empty_lead_id = uuid.uuid4()
        session.query(Lead).filter(Lead.id == empty_lead_id).delete()
        lead = Lead(
            id=empty_lead_id,
            organization_id=org.id,
            company_name="Empty Co",
            cnpj="11111111000111",
            city="Rio",
        )
        session.add(lead)
        session.commit()
        org_id = org.id
    finally:
        session.close()

    client, app = _client_with_stubs(org_id)
    try:
        resp = client.get(f"/api/leads/{empty_lead_id}/oportunidades")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["oportunidades"] == []
    finally:
        app.dependency_overrides.clear()