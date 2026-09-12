import asyncio
import os
import sys
from types import SimpleNamespace
from uuid import uuid4

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKERS = os.path.join(ROOT, "services", "workers", "src")
API = os.path.join(ROOT, "services", "api")
for path in (WORKERS, API):
    if path not in sys.path:
        sys.path.insert(0, path)

from src.services.crm_certification_service import CRMCertificationService  # noqa: E402
from src.services.crm_sync_service import CRMSyncService  # noqa: E402


class _Db:
    def __init__(self):
        self.added = []
        self.commits = 0

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1

    def refresh(self, _row):
        pass


class _Adapter:
    async def healthcheck(self):
        return {"status": "ok"}

    async def fetch_changes(self, *, organization_id, cursor=None):
        assert organization_id == "org-1"
        assert cursor is None
        return [SimpleNamespace(entity_id="remote-1")], "cursor-not-persisted"


class _BrokenAdapter:
    async def healthcheck(self):
        raise RuntimeError("token secret must never be persisted")

    async def fetch_changes(self, *, organization_id, cursor=None):
        raise AssertionError("must not read after failed auth")


def test_certification_exercises_auth_and_read_without_persisting_cursor(monkeypatch):
    connection = SimpleNamespace(
        id=uuid4(), provider="hubspot", last_health_status=None, last_health_at=None,
    )

    async def fake_adapter(_self, _connection_id):
        return connection, _Adapter()

    monkeypatch.setattr(CRMSyncService, "_adapter", fake_adapter)
    db = _Db()
    result = asyncio.run(CRMCertificationService(db, "org-1").run(connection.id, uuid4()))

    assert result.status == "PASSED"
    assert result.checks[0] == {"name": "authentication", "status": "passed"}
    assert result.checks[1]["name"] == "read_contract"
    assert result.checks[1]["status"] == "passed"
    assert result.checks[1]["sample_count"] == 1
    assert connection.last_health_status == "ok"
    assert db.commits == 1


def test_certification_does_not_persist_provider_error_message(monkeypatch):
    connection = SimpleNamespace(
        id=uuid4(), provider="pipedrive", last_health_status=None, last_health_at=None,
    )

    async def fake_adapter(_self, _connection_id):
        return connection, _BrokenAdapter()

    monkeypatch.setattr(CRMSyncService, "_adapter", fake_adapter)
    result = asyncio.run(CRMCertificationService(_Db(), "org-1").run(connection.id))

    assert result.status == "FAILED"
    assert result.checks == [{"name": "authentication", "status": "failed", "error": "RuntimeError"}]
    assert "secret" not in str(result.checks).lower()


def test_salesforce_certification_is_honest_about_incremental_read(monkeypatch):
    connection = SimpleNamespace(
        id=uuid4(), provider="salesforce", last_health_status=None, last_health_at=None,
    )

    class SalesforceAdapter(_Adapter):
        async def fetch_changes(self, *, organization_id, cursor=None):
            raise AssertionError("certification must not pretend generic SOQL exists")

    async def fake_adapter(_self, _connection_id):
        return connection, SalesforceAdapter()

    monkeypatch.setattr(CRMSyncService, "_adapter", fake_adapter)
    result = asyncio.run(CRMCertificationService(_Db(), "org-1").run(connection.id))

    assert result.status == "PASSED"
    assert result.checks[1]["status"] == "not_applicable"
    assert "SOQL" in result.checks[1]["note"]
