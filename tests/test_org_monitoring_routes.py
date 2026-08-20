"""Testes de regressão dos endpoints de monitoramento da organização.

Cobre `GET /orgs/{org_id}/webhook-logs` e `GET /orgs/{org_id}/job-logs` — a
dependência de acesso precisa ser `Depends(require_manager())` (fábrica, com
parênteses). Sem os parênteses o FastAPI resolve o guard interno como valor e
`actor.organization_id` estoura AttributeError → 500 (bug reportado no
docs/erros.md). O teste resolve as dependências de DB/org/membership mas
mantém o `require_manager` real para pegar exatamente essa classe de bug.
"""
import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.auth.dependencies import get_user_membership, get_user_organization
from src.db.dependencies import get_db
from src.db.models import OrganizationRole
from src.routes.orgs import router as orgs_router

ORG_ID = "6822b233-e9f2-4d20-b9fd-be4dba2e4c9d"


class _FakeQ:
    def filter(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def all(self):
        return []

    def first(self):
        return None


class _FakeDb:
    def query(self, *_args):
        return _FakeQ()

    def add(self, *_args):
        pass

    def flush(self):
        pass

    def commit(self):
        pass


def _member():
    return SimpleNamespace(
        id="u-1",
        role=OrganizationRole.OWNER,
        sales_role=None,
        user_id=uuid.uuid4(),
        organization_id=uuid.UUID(ORG_ID),
    )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(orgs_router, prefix="/api")
    app.dependency_overrides[get_db] = _FakeDb
    app.dependency_overrides[get_user_organization] = lambda: SimpleNamespace(id=uuid.UUID(ORG_ID))
    app.dependency_overrides[get_user_membership] = lambda: _member()
    return TestClient(app, raise_server_exceptions=False)


def test_webhook_logs_retorna_lista_vazia():
    resp = _client().get(f"/api/orgs/{ORG_ID}/webhook-logs?limit=50")
    assert resp.status_code == 200
    assert resp.json() == []


def test_job_logs_retorna_lista_vazia():
    resp = _client().get(f"/api/orgs/{ORG_ID}/job-logs?limit=50")
    assert resp.status_code == 200
    assert resp.json() == []


def test_webhook_logs_de_outra_org_retorna_404():
    outra_org = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    resp = _client().get(f"/api/orgs/{outra_org}/webhook-logs?limit=50")
    assert resp.status_code == 404