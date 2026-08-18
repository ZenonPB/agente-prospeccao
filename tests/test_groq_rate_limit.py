"""Testes do retry/pacing do provider Groq (Frente C).

Unidade pura (sem banco): monkeypatcha `create_http_client` e os settings de
rate-limit, garantindo que:
- 200 → chamada única;
- 429 com Retry-After → retenta e converge;
- 429 persistente → esgota as tentativas e retorna None (lead volta a NOVO).
"""
import asyncio

from services.provider_client import groq_json_chat


class FakeResponse:
    def __init__(self, status_code, json_body=None, headers=None):
        self.status_code = status_code
        self._json = json_body
        self.headers = headers or {}

    def json(self):
        return self._json


class FakeClient:
    """AsyncClient fake: reproduz a sequência de respostas, conta as chamadas."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.payloads = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None):
        idx = min(self.calls, len(self._responses) - 1)
        self.calls += 1
        if json is not None:
            self.payloads.append(dict(json))
        return self._responses[idx]


def _patch(monkeypatch, responses, interval=0.0, retries=2):
    from services import provider_client

    monkeypatch.setattr(provider_client.settings, "GROQ_MIN_INTERVAL_SECONDS", interval)
    monkeypatch.setattr(provider_client.settings, "GROQ_MAX_RETRIES", retries)
    monkeypatch.setattr(provider_client, "_last_groq_sent", 0.0)
    client = FakeClient(responses)
    monkeypatch.setattr(provider_client, "create_http_client", lambda *a, **k: client)
    return client


def _ok(body='{"ok": true}'):
    return FakeResponse(200, {"choices": [{"message": {"content": body}}]})


def test_success_single_call(monkeypatch):
    client = _patch(monkeypatch, [_ok()])
    result = asyncio.run(groq_json_chat("k", "m", "s", "u", "http://x", db=None))
    assert result == {"ok": True}
    assert client.calls == 1


def test_429_retry_after_succeeds(monkeypatch):
    client = _patch(
        monkeypatch,
        [FakeResponse(429, headers={"Retry-After": "0"}), _ok()],
        retries=2,
    )
    result = asyncio.run(groq_json_chat("k", "m", "s", "u", "http://x", db=None))
    assert result == {"ok": True}
    assert client.calls == 2


def test_429_exhausts_retries_returns_none(monkeypatch):
    client = _patch(
        monkeypatch,
        [FakeResponse(429, headers={"Retry-After": "0"})],
        retries=2,
    )
    result = asyncio.run(groq_json_chat("k", "m", "s", "u", "http://x", db=None))
    assert result is None
    assert client.calls == 2


def test_500_retries_without_retry_after(monkeypatch):
    client = _patch(
        monkeypatch,
        [FakeResponse(500), _ok()],
        retries=2,
    )
    result = asyncio.run(groq_json_chat("k", "m", "s", "u", "http://x", db=None))
    assert result == {"ok": True}
    assert client.calls == 2


def test_413_reduces_max_tokens_and_retries(monkeypatch):
    client = _patch(
        monkeypatch,
        [FakeResponse(413), _ok()],
        retries=2,
    )
    result = asyncio.run(
        groq_json_chat("k", "m", "s", "u", "http://x", db=None, max_tokens=6000)
    )
    assert result == {"ok": True}
    assert client.calls == 2
    assert client.payloads[0]["max_tokens"] == 6000
    assert client.payloads[1]["max_tokens"] < 6000


def test_413_exhausts_reductions_returns_none(monkeypatch):
    client = _patch(
        monkeypatch,
        [FakeResponse(413)],
        retries=2,
    )
    result = asyncio.run(
        groq_json_chat("k", "m", "s", "u", "http://x", db=None, max_tokens=6000)
    )
    assert result is None
    assert client.calls == 2
