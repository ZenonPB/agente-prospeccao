"""P1.1 — confiabilidade do provider HTTP de eventos.

Distinção obrigatória: erro do provider ≠ zero eventos. Contratos cobertos:
- sucesso retorna lista válida;
- falha HTTP/JSON levanta `EventProviderError` (após retry transitório);
- token de autenticação opcional vai no header;
- executor reporta `provider_status` por provider e rejeita eventos inválidos.
"""
import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "workers" / "src"))


class _FakeResponse:
    def __init__(self, json_data=None, status_code=200, raise_exc=None):
        self._json_data = json_data
        self.status_code = status_code
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc:
            raise self._raise_exc
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=httpx.Request("GET", "https://events.test"),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        if self._json_data is None:
            raise ValueError("invalid json")
        return self._json_data


class _FakeAsyncClient:
    """Substituto de httpx.AsyncClient com respostas pré-programadas."""

    responses: list = []
    requests: list = []

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, params=None, headers=None):
        _FakeAsyncClient.requests.append({"url": url, "params": params, "headers": headers})
        outcome = _FakeAsyncClient.responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture()
def fake_http(monkeypatch):
    _FakeAsyncClient.responses = []
    _FakeAsyncClient.requests = []
    monkeypatch.setattr(
        "services.prospecting.event_discovery.httpx.AsyncClient",
        _FakeAsyncClient,
    )
    return _FakeAsyncClient


def _provider(**kwargs):
    from services.prospecting.event_discovery import HttpEventDiscoveryProvider

    return HttpEventDiscoveryProvider("https://events.test/api", **kwargs)


class TestHttpEventDiscoveryProvider:
    def test_sucesso_retorna_lista_de_eventos(self, fake_http):
        fake_http.responses = [
            _FakeResponse({"events": [{"name": "Copa", "event_date": "2099-01-01", "source_url": "https://e/copa"}]})
        ]
        events = asyncio.run(_provider().discover())
        assert len(events) == 1
        assert events[0]["name"] == "Copa"

    def test_zero_eventos_nao_e_falha(self, fake_http):
        fake_http.responses = [_FakeResponse({"events": []})]
        events = asyncio.run(_provider().discover())
        assert events == []

    def test_erro_http_levanta_event_provider_error(self, fake_http):
        from services.prospecting.event_discovery import EventProviderError

        fake_http.responses = [_FakeResponse(status_code=500)]
        with pytest.raises(EventProviderError):
            asyncio.run(_provider(max_retries=0).discover())

    def test_json_invalido_levanta_event_provider_error(self, fake_http):
        from services.prospecting.event_discovery import EventProviderError

        fake_http.responses = [_FakeResponse(json_data=None)]
        with pytest.raises(EventProviderError):
            asyncio.run(_provider(max_retries=0).discover())

    def test_erro_transitorio_retenta_e_recupera(self, fake_http):
        fake_http.responses = [
            httpx.ConnectError("boom"),
            _FakeResponse({"events": [{"name": "Copa", "event_date": "2099-01-01", "source_url": "https://e/copa"}]}),
        ]
        events = asyncio.run(_provider(max_retries=1).discover())
        assert len(events) == 1
        assert len(fake_http.requests) == 2

    def test_erro_permanente_nao_passa_do_limite_de_tentativas(self, fake_http):
        from services.prospecting.event_discovery import EventProviderError

        fake_http.responses = [_FakeResponse(status_code=500), _FakeResponse(status_code=500)]
        with pytest.raises(EventProviderError):
            asyncio.run(_provider(max_retries=1).discover())
        assert len(fake_http.requests) == 2

    def test_token_de_autenticacao_vai_no_header(self, fake_http):
        fake_http.responses = [_FakeResponse({"events": []})]
        asyncio.run(_provider(token="segredo").discover())
        assert fake_http.requests[0]["headers"]["Authorization"] == "Bearer segredo"

    def test_sem_token_nao_envia_authorization(self, fake_http):
        fake_http.responses = [_FakeResponse({"events": []})]
        asyncio.run(_provider().discover())
        assert not (fake_http.requests[0]["headers"] or {}).get("Authorization")

    def test_resposta_com_shape_desconhecido_e_rejeitada(self, fake_http):
        from services.prospecting.event_discovery import EventProviderError

        fake_http.responses = [_FakeResponse({"unexpected": "shape"})]
        with pytest.raises(EventProviderError):
            asyncio.run(_provider().discover())


class TestExecutorProviderStatus:
    def _executor_with(self, provider):
        from services.prospecting.event_discovery import (
            EventDiscoveryExecutor, EventDiscoveryRegistry,
        )

        registry = EventDiscoveryRegistry()
        registry.register(provider)
        return EventDiscoveryExecutor(registry)

    def test_provider_falho_aparece_como_erro_nao_como_zero(self):
        from services.prospecting.event_discovery import EventProviderError

        class _Broken:
            name = "broken"

            async def discover(self, lead_context=None):
                raise EventProviderError("endpoint 500")

        result = self._executor_with(_Broken()).execute()
        assert result["provider_status"]["broken"] == "failed"
        assert "broken" in result["provider_errors"]
        assert result["unique_count"] == 0

    def test_provider_vazio_aparece_como_empty(self):
        class _Empty:
            name = "empty"

            async def discover(self, lead_context=None):
                return []

        result = self._executor_with(_Empty()).execute()
        assert result["provider_status"]["empty"] == "empty"

    def test_provider_ok_aparece_como_ok(self):
        class _Ok:
            name = "ok"

            async def discover(self, lead_context=None):
                return [{
                    "name": "Copa",
                    "event_date": "2099-01-01",
                    "source_url": "https://e/copa",
                    "organizer": "Federação X",
                }]

        result = self._executor_with(_Ok()).execute()
        assert result["provider_status"]["ok"] == "ok"
        assert result["unique_count"] == 1

    def test_provider_ausente_no_registry_aparece_como_skipped(self):
        from services.prospecting.event_discovery import (
            EventDiscoveryExecutor, EventDiscoveryRegistry,
        )

        registry = EventDiscoveryRegistry()
        result = EventDiscoveryExecutor(registry).execute(
            plan={"providers": [{"type": "fantasma"}]},
        )
        assert result["provider_status"]["fantasma"] == "skipped"

    def test_provider_metrics_expõem_contrato_operacional(self):
        class _Ok:
            name = "ok"

            async def discover(self, lead_context=None):
                return [{
                    "name": "Copa",
                    "event_date": "2099-01-01",
                    "source_url": "https://e/copa-metrics",
                    "organizer": "Federação X",
                }]

        metrics = self._executor_with(_Ok()).execute()["provider_metrics"]["ok"]

        assert metrics["status"] == "success"
        assert metrics["result_count"] == 1
        assert isinstance(metrics["duration_ms"], int)
        assert metrics["error_code"] is None
        assert metrics["retryable"] is False

    def test_falha_de_provider_preserva_error_code_e_retryable(self):
        from services.prospecting.event_discovery import EventProviderError

        class _Broken:
            name = "broken-metrics"

            async def discover(self, lead_context=None):
                raise EventProviderError("endpoint 503")

        metrics = self._executor_with(_Broken()).execute()["provider_metrics"]["broken-metrics"]

        assert metrics["status"] == "failed"
        assert metrics["result_count"] == 0
        assert metrics["error_code"] == "EventProviderError"
        assert metrics["retryable"] is True

    def test_evento_invalido_e_rejeitado_e_contado(self):
        class _Mixed:
            name = "mixed"

            async def discover(self, lead_context=None):
                return [
                    {"name": "Bom", "event_date": "2099-01-01", "source_url": "https://e/bom"},
                    {"name": "", "event_date": "2099-01-01", "source_url": "https://e/x"},
                    {"name": "Sem data", "event_date": "", "source_url": "https://e/y"},
                ]

        result = self._executor_with(_Mixed()).execute()
        assert result["unique_count"] == 1
        assert result["rejected_count"] == 2
        assert all(ev["name"] == "Bom" for ev in result["unique_events"])
