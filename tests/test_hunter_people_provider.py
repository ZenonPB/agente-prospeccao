"""Contrato do adapter Hunter para descoberta de pessoas."""

import asyncio
from types import SimpleNamespace

import httpx


def _response(status_code, payload=None, headers=None):
    return httpx.Response(
        status_code,
        json=payload,
        headers=headers,
        request=httpx.Request("GET", "https://api.hunter.io/v2/domain-search"),
    )


class TestHunterPeopleProvider:
    def test_converte_domain_search_em_pessoas_normalizadas(self):
        from services.prospecting.hunter_people_provider import HunterPeopleProvider

        calls = []

        async def request(**kwargs):
            calls.append(kwargs)
            return _response(200, {"data": {"emails": [{
                "value": "ana@empresa.com.br",
                "type": "personal",
                "first_name": "Ana",
                "last_name": "Silva",
                "position": "Engineering Manager",
                "confidence": 86,
                "sources": [{"uri": "https://empresa.com.br/equipe"}],
            }]}})

        provider = HunterPeopleProvider("secret", request=request)
        people = asyncio.run(provider.search("empresa.com.br", ["Engineering Manager"]))

        assert people[0]["name"] == "Ana Silva"
        assert people[0]["email"] == "ana@empresa.com.br"
        assert people[0]["source"] == "hunter"
        assert people[0]["sources"] == ["https://empresa.com.br/equipe"]
        assert calls[0]["params"]["domain"] == "empresa.com.br"
        assert calls[0]["params"]["type"] == "personal"
        assert calls[0]["headers"] == {"X-API-KEY": "secret"}

    def test_retorna_falha_de_configuracao_sem_chamar_http(self):
        from services.prospecting.hunter_people_provider import HunterPeopleProvider, HunterProviderError

        called = []

        async def request(**kwargs):
            called.append(kwargs)
            return _response(200, {})

        provider = HunterPeopleProvider("", request=request)

        try:
            asyncio.run(provider.search("empresa.com.br", ["CEO"]))
        except HunterProviderError as exc:
            assert exc.status == "disabled"
        else:
            raise AssertionError("chave vazia deveria desabilitar o provider")
        assert called == []

    def test_retorna_quota_exceeded_em_429(self):
        from services.prospecting.hunter_people_provider import HunterPeopleProvider, HunterProviderError

        async def request(**kwargs):
            return _response(429, {"errors": [{"code": "rate_limit"}]})

        provider = HunterPeopleProvider("secret", request=request, max_retries=0)

        try:
            asyncio.run(provider.search("empresa.com.br", ["CEO"]))
        except HunterProviderError as exc:
            assert exc.status == "quota_exceeded"
            assert exc.retryable is True
        else:
            raise AssertionError("429 deveria produzir erro observável")

    def test_retry_em_erro_transitorio(self):
        from services.prospecting.hunter_people_provider import HunterPeopleProvider

        calls = []

        async def request(**kwargs):
            calls.append(kwargs)
            return _response(500 if len(calls) == 1 else 200, {"data": {"emails": []}})

        provider = HunterPeopleProvider("secret", request=request, max_retries=1, retry_delay=0)
        assert asyncio.run(provider.search("empresa.com.br", ["CEO"])) == []
        assert len(calls) == 2
