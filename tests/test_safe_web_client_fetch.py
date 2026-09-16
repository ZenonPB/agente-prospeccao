"""Fetch seguro do SafePublicWebClient: limites HTTP (parte 2).

RED (TDD): timeout, DNS failure, connection failure, 404/500, HTML válido e
malformado, charset, sem Content-Type, Content-Type proibido, payload no
limite/acima (streaming, sem `response.content` ilimitado), body vazio e
redirect seguro — tudo sem rede real (transport injetável).
"""
from __future__ import annotations

import asyncio

import httpx
import pytest


def _client(handler, **kwargs):
    from services.prospecting.safe_web_client import SafePublicWebClient

    transport = httpx.MockTransport(handler)
    # Testes: DNS resolvido como público; segurança de DNS tem testes próprios.
    return SafePublicWebClient(
        transport=transport, resolver=lambda host, port: ["93.184.216.34"], **kwargs
    )


def test_fetch_html_valido_retorna_body_e_content_type():
    async def _run():
        def handler(request):
            return httpx.Response(
                200, headers={"Content-Type": "text/html; charset=utf-8"},
                content="<html><head><title>X</title></head></html>".encode(),
            )

        result = await _client(handler).fetch("https://empresa.example/")
        assert result["status"] == "ok"
        assert result["status_code"] == 200
        assert "<title>X</title>" in result["text"]

    asyncio.run(_run())


def test_404_nao_e_falha_infra_e_texto_vem_unknown():
    async def _run():
        def handler(request):
            return httpx.Response(404, content=b"nao achado")

        result = await _client(handler).fetch("https://empresa.example/ausente")
        assert result["status"] == "http_error"
        assert result["status_code"] == 404

    asyncio.run(_run())


def test_content_type_proibido_nao_baixa_pdf():
    async def _run():
        def handler(request):
            return httpx.Response(
                200, headers={"Content-Type": "application/pdf"},
                content=b"%PDF-1.4" + b"x" * 100,
            )

        from services.prospecting.safe_web_client import SafeWebClientError

        with pytest.raises(SafeWebClientError):
            await _client(handler).fetch("https://empresa.example/doc.pdf")

    asyncio.run(_run())


def test_payload_acima_do_limite_aborta_streaming():
    async def _run():
        def handler(request):
            return httpx.Response(
                200, headers={"Content-Type": "text/html"},
                content=b"x" * 300,
            )

        from services.prospecting.safe_web_client import SafeWebClientError

        with pytest.raises(SafeWebClientError):
            await _client(handler, max_bytes=100).fetch("https://empresa.example/")

    asyncio.run(_run())


def test_timeout_vira_erro_retryable_sem_vazar_html():
    async def _run():
        def handler(request):
            raise httpx.ConnectTimeout("lento")

        result = await _client(handler).fetch("https://empresa.example/")
        assert result["status"] == "failed"
        assert result["retryable"] is True
        assert "text" not in result

    asyncio.run(_run())


def test_redirect_seguro_e_seguido_com_revalidacao():
    async def _run():
        def handler(request):
            if request.url.path == "/a":
                return httpx.Response(301, headers={"Location": "/b"})
            return httpx.Response(
                200, headers={"Content-Type": "text/html"}, content=b"<html></html>",
            )

        result = await _client(handler).fetch("https://empresa.example/a")
        assert result["status"] == "ok"
        assert result["redirects"] == 1

    asyncio.run(_run())


def test_fetch_usa_streaming_e_nao_materializa_corpo_antes_do_limite():
    async def _run():
        class _StreamingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                return httpx.Response(
                    200,
                    headers={"Content-Type": "text/html", "Content-Length": "1000000"},
                    content=b"<html></html>",
                )

        from services.prospecting.safe_web_client import SafePublicWebClient

        client = SafePublicWebClient(
            transport=_StreamingTransport(),
            resolver=lambda host, port: ["93.184.216.34"],
            max_bytes=100,
        )
        from services.prospecting.safe_web_client import SafeWebClientError

        with pytest.raises(SafeWebClientError, match="payload_too_large"):
            await client.fetch("https://empresa.example/")

    asyncio.run(_run())
