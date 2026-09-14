from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import httpx
import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
API_SRC = os.path.join(ROOT, "services", "api", "src")
WORKERS_SRC = os.path.join(ROOT, "services", "workers", "src")
for path in (API_SRC, WORKERS_SRC):
    if path not in sys.path:
        sys.path.insert(0, path)

from src.services.provider_diagnostics_service import (  # noqa: E402
    ProviderDiagnosticsService,
    classify_provider_status,
)


class _Query:
    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return SimpleNamespace(id="configured")


class _Db:
    def query(self, *_args, **_kwargs):
        return _Query()


class _Response:
    def __init__(self, status_code: int):
        self.status_code = status_code


class _Client:
    def __init__(self, statuses: dict[str, int]):
        self.statuses = statuses
        self.calls: list[tuple[str, str]] = []

    async def post(self, url: str, **_kwargs):
        self.calls.append(("POST", url))
        return _Response(self.statuses["google"])

    async def get(self, url: str, **_kwargs):
        self.calls.append(("GET", url))
        if "groq.com" in url:
            return _Response(self.statuses["groq"])
        return _Response(self.statuses["hunter"])


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(200, "ok"), (204, "ok"), (401, "invalid_key"), (403, "invalid_key"), (429, "quota_limited"), (500, "unavailable"), (400, "rejected")],
)
def test_classify_provider_status(status_code: int, expected: str):
    assert classify_provider_status(status_code) == expected


@pytest.mark.asyncio
async def test_diagnostics_is_safe_and_requires_google_and_groq(monkeypatch):
    secret = "never-leak-this-secret"

    async def resolve_key(_db, _organization_id, _key_name):
        return secret

    monkeypatch.setattr(
        "src.services.provider_diagnostics_service.SecretService.resolve_key",
        resolve_key,
    )
    client = _Client({"google": 200, "groq": 200, "hunter": 429})
    result = await ProviderDiagnosticsService().diagnose(
        _Db(), "00000000-0000-0000-0000-000000000001", client=client
    )

    assert result["ready_for_basic_prospecting"] is True
    assert {item["provider"]: item["status"] for item in result["providers"]} == {
        "google": "ok",
        "groq": "ok",
        "hunter": "quota_limited",
    }
    assert secret not in repr(result)
    assert all("body" not in item for item in result["providers"])


@pytest.mark.asyncio
async def test_diagnostics_fail_closed_when_essential_provider_is_invalid(monkeypatch):
    async def resolve_key(_db, _organization_id, _key_name):
        return "safe-placeholder"

    monkeypatch.setattr(
        "src.services.provider_diagnostics_service.SecretService.resolve_key",
        resolve_key,
    )
    result = await ProviderDiagnosticsService().diagnose(
        _Db(),
        "00000000-0000-0000-0000-000000000001",
        client=_Client({"google": 403, "groq": 200, "hunter": 200}),
    )
    assert result["ready_for_basic_prospecting"] is False


@pytest.mark.asyncio
async def test_diagnostics_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Provider não suportado"):
        await ProviderDiagnosticsService().diagnose(_Db(), "org", ["unknown"], client=_Client({}))


@pytest.mark.asyncio
async def test_diagnostics_reports_timeout_without_exposing_exception(monkeypatch):
    async def resolve_key(_db, _organization_id, _key_name):
        return "safe-placeholder"

    class TimeoutClient:
        async def get(self, *_args, **_kwargs):
            raise httpx.ReadTimeout("timeout")

        async def post(self, *_args, **_kwargs):
            raise httpx.ReadTimeout("timeout")

    monkeypatch.setattr(
        "src.services.provider_diagnostics_service.SecretService.resolve_key",
        resolve_key,
    )
    result = await ProviderDiagnosticsService().diagnose(
        _Db(), "org", ["google"], client=TimeoutClient()
    )
    assert result["providers"][0]["status"] == "timeout"
    assert "safe-placeholder" not in repr(result)
