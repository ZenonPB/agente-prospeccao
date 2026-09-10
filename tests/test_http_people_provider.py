"""Contrato do provider HTTP especializado para descoberta de pessoas.

Seam público: `HttpPeopleProvider.search(domain, titles)`.
Federação genérica opt-in (mesmo padrão do `HttpEventDiscoveryProvider`):
a organização pluga qualquer fonte especializada (Apollo/Clay/Snov/interna)
via endpoint JSON próprio, com quota por org, retry e provenance.
Lista vazia é resposta válida sem resultado — nunca falha silenciosa.
"""

import asyncio

import httpx


def _response(status_code, payload=None):
    kwargs = {"request": httpx.Request("GET", "https://pessoas.example.com/search")}
    if payload is not None:
        return httpx.Response(status_code, json=payload, **kwargs)
    return httpx.Response(status_code, **kwargs)


class TestHttpPeopleProvider:
    def test_normaliza_pessoas_com_provenance_sem_verificacao_inventada(self):
        from services.prospecting.http_people_provider import HttpPeopleProvider

        calls = []

        async def request(**kwargs):
            calls.append(kwargs)
            return _response(200, {"people": [{
                "name": "Ana Silva",
                "jobTitle": "Engineering Manager",
                "email": "ana@empresa.com.br",
                "linkedin_url": "https://www.linkedin.com/in/ana-silva",
                "confidence": 82,
            }]})

        provider = HttpPeopleProvider("https://pessoas.example.com/search", request=request)
        people = asyncio.run(provider.search("empresa.com.br", ["Engineering Manager"]))

        assert people == [{
            "name": "Ana Silva",
            "role": "Engineering Manager",
            "email": "ana@empresa.com.br",
            "phone": None,
            "linkedin_url": "https://www.linkedin.com/in/ana-silva",
            "source": "people_http",
            "sources": ["https://pessoas.example.com/search"],
            "domain": "empresa.com.br",
            "confidence": 82,
            "identity_confidence": 0.0,
            "email_verified": False,
        }]
        assert calls[0]["params"]["domain"] == "empresa.com.br"
        assert "engineering" in calls[0]["params"]["titles"].lower()

    def test_aceita_lista_direta_e_mapa_de_campos_alternativos(self):
        from services.prospecting.http_people_provider import HttpPeopleProvider

        async def request(**kwargs):
            return _response(200, [{
                "name": "Bruno",
                "title": "CEO",
                "telephone": "+55 11 99999-0000",
                "sameAs": ["https://www.linkedin.com/in/bruno"],
            }])

        provider = HttpPeopleProvider("https://pessoas.example.com/search", request=request)
        people = asyncio.run(provider.search("empresa.com.br", ["ceo"]))

        assert len(people) == 1
        assert people[0]["role"] == "CEO"
        assert people[0]["phone"] == "+55 11 99999-0000"
        assert people[0]["linkedin_url"] == "https://www.linkedin.com/in/bruno"
        assert people[0]["email_verified"] is False

    def test_resposta_vazia_e_valida_nao_falha(self):
        from services.prospecting.http_people_provider import HttpPeopleProvider

        async def request(**kwargs):
            return _response(200, {"people": []})

        provider = HttpPeopleProvider("https://pessoas.example.com/search", request=request)
        assert asyncio.run(provider.search("empresa.com.br", ["CEO"])) == []

    def test_pula_item_sem_nome_sem_inventar_pessoa(self):
        from services.prospecting.http_people_provider import HttpPeopleProvider

        async def request(**kwargs):
            return _response(200, {"people": [
                {"email": "sem-nome@empresa.com.br"},
                {"name": "  ", "role": "CEO"},
                {"name": "Real", "role": "CTO"},
            ]})

        provider = HttpPeopleProvider("https://pessoas.example.com/search", request=request)
        people = asyncio.run(provider.search("empresa.com.br", ["cto"]))

        assert [person["name"] for person in people] == ["Real"]

    def test_falha_de_rede_levanta_failed_retryable(self):
        from services.prospecting.http_people_provider import (
            HttpPeopleProvider,
            HttpPeopleProviderError,
        )

        async def request(**kwargs):
            raise httpx.ConnectError("dns")

        provider = HttpPeopleProvider(
            "https://pessoas.example.com/search", request=request, max_retries=0,
        )

        try:
            asyncio.run(provider.search("empresa.com.br", ["CEO"]))
        except HttpPeopleProviderError as exc:
            assert exc.status == "failed"
            assert exc.retryable is True
        else:
            raise AssertionError("falha de rede deveria levantar failed retryable")

    def test_429_vira_quota_exceeded(self):
        from services.prospecting.http_people_provider import (
            HttpPeopleProvider,
            HttpPeopleProviderError,
        )

        async def request(**kwargs):
            return _response(429, {"error": "rate limit"})

        provider = HttpPeopleProvider(
            "https://pessoas.example.com/search", request=request, max_retries=0,
        )

        try:
            asyncio.run(provider.search("empresa.com.br", ["CEO"]))
        except HttpPeopleProviderError as exc:
            assert exc.status == "quota_exceeded"
            assert exc.retryable is True
        else:
            raise AssertionError("429 deveria produzir quota_exceeded")

    def test_json_invalido_levanta_failed_sem_retry(self):
        from services.prospecting.http_people_provider import (
            HttpPeopleProvider,
            HttpPeopleProviderError,
        )

        async def request(**kwargs):
            return httpx.Response(
                200,
                text="nao-json",
                request=httpx.Request("GET", "https://pessoas.example.com/search"),
            )

        provider = HttpPeopleProvider("https://pessoas.example.com/search", request=request)

        try:
            asyncio.run(provider.search("empresa.com.br", ["CEO"]))
        except HttpPeopleProviderError as exc:
            assert exc.status == "failed"
            assert exc.retryable is False
        else:
            raise AssertionError("JSON inválido deveria levantar failed")

    def test_payload_sem_lista_levanta_failed(self):
        from services.prospecting.http_people_provider import (
            HttpPeopleProvider,
            HttpPeopleProviderError,
        )

        async def request(**kwargs):
            return _response(200, {"resultado": "sem chave people"})

        provider = HttpPeopleProvider("https://pessoas.example.com/search", request=request)

        try:
            asyncio.run(provider.search("empresa.com.br", ["CEO"]))
        except HttpPeopleProviderError as exc:
            assert exc.status == "failed"
        else:
            raise AssertionError("payload sem lista deveria levantar failed")

    def test_sem_endpoint_desabilita_sem_http(self):
        from services.prospecting.http_people_provider import (
            HttpPeopleProvider,
            HttpPeopleProviderError,
        )

        called = []

        async def request(**kwargs):
            called.append(kwargs)
            return _response(200, {"people": []})

        for endpoint in ("", "  ", None):
            try:
                asyncio.run(HttpPeopleProvider(endpoint, request=request).search(
                    "empresa.com.br", ["CEO"],
                ))
            except HttpPeopleProviderError as exc:
                assert exc.status == "disabled"
            else:
                raise AssertionError("sem endpoint deveria desabilitar o provider")
        assert called == []

    def test_quota_esgotada_impede_consulta(self):
        from services.prospecting.http_people_provider import (
            HttpPeopleProvider,
            HttpPeopleProviderError,
        )

        called = []

        async def request(**kwargs):
            called.append(kwargs)
            return _response(200, {"people": []})

        provider = HttpPeopleProvider(
            "https://pessoas.example.com/search",
            request=request,
            can_consume=lambda: False,
        )

        try:
            asyncio.run(provider.search("empresa.com.br", ["CEO"]))
        except HttpPeopleProviderError as exc:
            assert exc.status == "quota_exceeded"
        else:
            raise AssertionError("quota esgotada deveria impedir a consulta")
        assert called == []

    def test_dominio_invalido_rejeitado_sem_http(self):
        from services.prospecting.http_people_provider import (
            HttpPeopleProvider,
            HttpPeopleProviderError,
        )

        called = []

        async def request(**kwargs):
            called.append(kwargs)
            return _response(200, {"people": []})

        provider = HttpPeopleProvider("https://pessoas.example.com/search", request=request)

        for domain in ("localhost", "127.0.0.1", "", "sem-ponto"):
            try:
                asyncio.run(provider.search(domain, ["CEO"]))
            except HttpPeopleProviderError as exc:
                assert exc.status == "invalid_request"
            else:
                raise AssertionError(f"domínio {domain!r} deveria ser rejeitado")
        assert called == []

    def test_retry_em_erro_transitorio(self):
        from services.prospecting.http_people_provider import HttpPeopleProvider

        calls = []

        async def request(**kwargs):
            calls.append(kwargs)
            return _response(500 if len(calls) == 1 else 200, {"people": []})

        provider = HttpPeopleProvider(
            "https://pessoas.example.com/search",
            request=request,
            max_retries=1,
            retry_delay=0,
        )
        assert asyncio.run(provider.search("empresa.com.br", ["CEO"])) == []
        assert len(calls) == 2

    def test_envia_bearer_quando_token_configurado(self):
        from services.prospecting.http_people_provider import HttpPeopleProvider

        calls = []

        async def request(**kwargs):
            calls.append(kwargs)
            return _response(200, {"people": []})

        provider = HttpPeopleProvider(
            "https://pessoas.example.com/search", token="tok-123", request=request,
        )
        asyncio.run(provider.search("empresa.com.br", ["CEO"]))

        assert calls[0]["headers"] == {"Authorization": "Bearer tok-123"}

    def test_consume_quota_apenas_apos_resposta_valida(self):
        from services.prospecting.http_people_provider import HttpPeopleProvider

        consumed = []

        async def request(**kwargs):
            return _response(200, {"people": []})

        provider = HttpPeopleProvider(
            "https://pessoas.example.com/search",
            request=request,
            can_consume=lambda: True,
            consume=lambda: consumed.append(True),
        )
        assert asyncio.run(provider.search("empresa.com.br", ["CEO"])) == []
        assert consumed == [True]


class TestHttpPeopleProviderFactoryOptIn:
    def test_sem_endpoint_ou_sem_quota_nao_registra(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        from services.contact_enrichment_service import ContactEnrichmentService

        organization = MagicMock(api_quota={})
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = organization

        with patch(
            "services.secret_service.SecretService.resolve_key",
            new=AsyncMock(return_value=None),
        ):
            service = asyncio.run(ContactEnrichmentService.for_organization(db, "org-1"))

        assert "people_http" not in service.people_registry.list_providers()

    def test_com_endpoint_e_quota_registra_entre_site_e_hunter(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock, patch

        from services.contact_enrichment_service import ContactEnrichmentService
        from services.prospecting import http_people_provider as http_module

        organization = MagicMock(api_quota={
            "HUNTER_API_KEY": 50,
            "WEBSITE_PEOPLE_PROVIDER": 10,
            "PEOPLE_DISCOVERY_HTTP": 20,
        })
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = organization

        with (
            patch(
                "services.secret_service.SecretService.resolve_key",
                new=AsyncMock(return_value="org-secret"),
            ),
            patch.object(
                http_module.settings, "PEOPLE_DISCOVERY_URL",
                "https://pessoas.example.com/search",
            ),
            patch.object(http_module.settings, "PEOPLE_DISCOVERY_TOKEN", ""),
        ):
            service = asyncio.run(ContactEnrichmentService.for_organization(db, "org-1"))

        assert service.people_registry.list_providers() == [
            "website_people", "people_http", "hunter",
        ]

    def test_quota_http_e_consumo_mas_nao_secret(self):
        from services.secret_service import KEY_NAMES, QUOTA_KEY_NAMES

        assert "PEOPLE_DISCOVERY_HTTP" not in KEY_NAMES
        assert "PEOPLE_DISCOVERY_HTTP" in QUOTA_KEY_NAMES


class TestHttpPeopleWaterfallIntegration:
    def test_waterfall_consume_http_com_role_fit_buyer_role_e_custo(self):
        import asyncio

        import httpx

        from services.prospecting.http_people_provider import HttpPeopleProvider
        from services.prospecting.people_provider_registry import PeopleProviderRegistry

        async def request(**kwargs):
            return httpx.Response(
                200,
                json={"people": [{
                    "name": "Carla Souza",
                    "jobTitle": "Engineering Manager",
                    "email": "carla@empresa.com.br",
                    "confidence": 88,
                    "identity_confidence": 80,
                }]},
                request=httpx.Request("GET", "https://pessoas.example.com/search"),
            )

        registry = PeopleProviderRegistry([
            HttpPeopleProvider("https://pessoas.example.com/search", request=request),
        ])
        result = asyncio.run(registry.waterfall_search(
            "empresa.com.br",
            ["Engineering Manager"],
            min_contact_confidence=70,
            min_identity_confidence=70,
            required_buyer_role="TECHNICAL_BUYER",
        ))

        assert result["status"] == "success"
        assert result["early_stopped"] is True
        assert result["cost_spent"] == 0.5
        assert result["providers_attempted"] == ["people_http"]
        person = result["people"][0]
        assert person["role_fit_status"] == "matched"
        assert person["buyer_role"] == "TECHNICAL_BUYER"
        assert person["buyer_role_status"] == "matched"
        assert result["buyer_role"]["matched"] == 1
