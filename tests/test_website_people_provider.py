"""Testes do provider passivo de pessoas publicadas no site."""

import asyncio

import httpx


def _response(html: str, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        text=html,
        request=httpx.Request("GET", "https://empresa.com.br/"),
    )


def test_extrai_person_jsonld_com_provenance_e_sem_verificacao_inventada():
    from services.prospecting.website_people_provider import WebsitePeopleProvider

    html = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Person","name":"Ana Silva",
     "jobTitle":"Engineering Manager","email":"ana@empresa.com.br",
     "sameAs":["https://www.linkedin.com/in/ana-silva"]}
    </script>
    """

    async def request(**kwargs):
        assert kwargs["url"] == "https://empresa.com.br/"
        return _response(html)

    people = asyncio.run(WebsitePeopleProvider(request=request, max_pages=1).search(
        "https://empresa.com.br", ["engineering_manager"],
    ))

    assert people == [{
        "name": "Ana Silva",
        "role": "Engineering Manager",
        "email": "ana@empresa.com.br",
        "phone": None,
        "linkedin_url": "https://www.linkedin.com/in/ana-silva",
        "source": "company_site",
        "sources": ["https://empresa.com.br/"],
        "confidence": 85,
        "email_verified": False,
    }]


def test_ignora_jsonld_que_nao_e_person_e_deduplica_pessoas():
    from services.prospecting.website_people_provider import WebsitePeopleProvider

    html = """
    <script type="application/ld+json">
    [{"@type":"Organization","name":"Empresa"},
     {"@type":"Person","name":"Bruno","jobTitle":"CEO"},
     {"@type":"Person","name":"Bruno","jobTitle":"CEO"}]
    </script>
    """

    async def request(**kwargs):
        return _response(html)

    people = asyncio.run(WebsitePeopleProvider(request=request, max_pages=1).search(
        "empresa.com.br", ["ceo"],
    ))

    assert len(people) == 1
    assert people[0]["name"] == "Bruno"


def test_nao_consulta_quando_quota_esta_esgotada():
    from services.prospecting.website_people_provider import WebsitePeopleProvider, WebsiteProviderError

    called = []

    async def request(**kwargs):
        called.append(kwargs)
        return _response("")

    provider = WebsitePeopleProvider(request=request, can_consume=lambda: False)

    try:
        asyncio.run(provider.search("empresa.com.br", ["ceo"]))
    except WebsiteProviderError as exc:
        assert exc.status == "quota_exceeded"
    else:
        raise AssertionError("quota esgotada deveria impedir a consulta")
    assert called == []


def test_rejeita_dominio_invalido_sem_http():
    from services.prospecting.website_people_provider import WebsitePeopleProvider, WebsiteProviderError

    try:
        asyncio.run(WebsitePeopleProvider().search("localhost", ["ceo"]))
    except WebsiteProviderError as exc:
        assert exc.status == "invalid_request"
    else:
        raise AssertionError("domínio inválido deveria ser rejeitado")


def test_rejeita_ip_privado_para_evitar_ssrf():
    from services.prospecting.website_people_provider import WebsitePeopleProvider, WebsiteProviderError

    try:
        asyncio.run(WebsitePeopleProvider().search("127.0.0.1", ["ceo"]))
    except WebsiteProviderError as exc:
        assert exc.status == "invalid_request"
    else:
        raise AssertionError("IP privado não pode ser consultado")


def test_ignora_redirecionamento_para_dominio_externo():
    from services.prospecting.website_people_provider import WebsitePeopleProvider

    async def request(**kwargs):
        return httpx.Response(
            200,
            text="<script type='application/ld+json'>{\"@type\":\"Person\",\"name\":\"Fora\"}</script>",
            request=httpx.Request("GET", "https://outro-dominio.example/"),
        )

    people = asyncio.run(WebsitePeopleProvider(request=request, max_pages=1).search(
        "empresa.com.br", ["ceo"],
    ))

    assert people == []


def test_consume_uma_unidade_por_execucao_com_paginas_publicas():
    from services.prospecting.website_people_provider import WebsitePeopleProvider

    consumed = []

    async def request(**kwargs):
        return _response("<html><body>Sem dados estruturados</body></html>")

    people = asyncio.run(WebsitePeopleProvider(
        request=request,
        can_consume=lambda: True,
        consume=lambda: consumed.append(True),
        max_pages=3,
    ).search("empresa.com.br", ["ceo"]))

    assert people == []
    assert consumed == [True]