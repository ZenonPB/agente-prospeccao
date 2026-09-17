"""Regressões dos defaults HTTP compartilhados pelos providers."""
from __future__ import annotations

import asyncio

import httpx

from services.provider_client import create_http_client, groq_json_chat


def test_http_client_usa_timeout_por_fase():
    client = create_http_client(timeout=37.0)
    try:
        assert client.timeout.connect == 10.0
        assert client.timeout.read == 37.0
        assert client.timeout.write == 20.0
        assert client.timeout.pool == 10.0
    finally:
        asyncio.run(client.aclose())


def test_erro_de_rede_falha_suave_sem_retry_infinito(monkeypatch):
    """DNS/conexão indisponível não derruba o lote nem entra em loop de retry."""
    from services import provider_client

    calls = 0

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            raise httpx.ConnectError("dns indisponível")

    monkeypatch.setattr(provider_client, "create_http_client", lambda *a, **k: FailingClient())
    monkeypatch.setattr(provider_client.settings, "GROQ_MIN_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(provider_client, "_last_groq_sent", 0.0)

    result = asyncio.run(groq_json_chat("k", "m", "s", "u", "https://example.invalid", db=None))

    assert result is None
    assert calls == 1
