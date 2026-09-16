"""SafePublicWebClient: HTTP público e seguro para a 1D (parte 1: contrato).

RED (TDD): SSRF não-negociável — IPs privados, localhost, metadata,
redirect público→privado, schemes inválidos e userinfo devem ser bloqueados.
Segue o padrão canônico do repo (`external_intent_feed_provider`):
allowlist de scheme, DNS resolve-all, revalidação por hop de redirect.

Ajuste aprovado: o caminho 1D usa este client; consumidores legados migram
só se a substituição for pequena e behavior-preserving (dívida explícita).
"""
from __future__ import annotations

import pytest

BLOCKED_URLS = [
    "http://127.0.0.1/",
    "http://localhost/",
    "http://[::1]/",
    "http://10.0.0.5/",
    "http://172.16.0.9/",
    "http://192.168.1.10/",
    "http://169.254.169.254/latest/meta-data/",
    "file:///etc/passwd",
    "ftp://example.com/x",
    "gopher://example.com/",
    "data:text/plain,oi",
    "http://user:pass@example.com/",
    "http://example.com:99999/",
    "http:///",
]


@pytest.mark.parametrize("url", BLOCKED_URLS)
def test_urls_hostis_sao_rejeitadas_sem_request(url):
    from services.prospecting.safe_web_client import (
        SafeWebClientError, SafePublicWebClient,
    )

    client = SafePublicWebClient()
    with pytest.raises(SafeWebClientError):
        client.validate_url(url)


def test_hostname_localhost_e_rejeitado():
    from services.prospecting.safe_web_client import (
        SafeWebClientError, SafePublicWebClient,
    )

    with pytest.raises(SafeWebClientError):
        SafePublicWebClient().validate_url("https://localhost.empresa.com/")


def test_dns_resolvendo_privado_e_rejeitado():
    from services.prospecting.safe_web_client import (
        SafeWebClientError, SafePublicWebClient,
    )

    client = SafePublicWebClient()
    with pytest.raises(SafeWebClientError):
        client.validate_destination("public.example", ["93.184.216.34", "10.0.0.1"])


@pytest.mark.parametrize(
    ("url", "expected_port"),
    [("http://example.com/", 80), ("https://example.com/", 443)],
)
def test_dns_usa_porta_padrao_do_scheme(url, expected_port):
    import asyncio

    from services.prospecting.safe_web_client import SafePublicWebClient

    seen = []

    async def _run():
        client = SafePublicWebClient(
            resolver=lambda host, port: seen.append((host, port)) or ["93.184.216.34"],
        )
        await client._check_destination(url)

    asyncio.run(_run())
    assert seen == [("example.com", expected_port)]


def test_redirect_publico_para_privado_e_bloqueado():
    import asyncio

    from services.prospecting.safe_web_client import (
        SafePublicWebClient, SafeWebClientError,
    )

    async def _run():
        client = SafePublicWebClient()
        with pytest.raises(SafeWebClientError):
            await client._check_redirect(
                "http://public.example/", "http://127.0.0.1:5432/", hop=1,
            )

    asyncio.run(_run())


def test_redirect_excessivo_e_bloqueado():
    import asyncio

    from services.prospecting.safe_web_client import (
        SafePublicWebClient, SafeWebClientError,
    )

    async def _run():
        client = SafePublicWebClient(max_redirects=3)
        with pytest.raises(SafeWebClientError):
            await client._check_redirect(
                "http://a.example/", "http://b.example/", hop=4,
            )

    asyncio.run(_run())
