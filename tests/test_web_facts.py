"""Extração determinística de FACTs web (parte 3 da 1D).

RED (TDD): title, meta description, canonical, links contato/sobre/serviços,
email/telefone corporativo público, social links, JSON-LD básico — e,
sobretudo, UNKNOWN != FALSE: timeout/falha nunca vira `website_absent`.
"""
from __future__ import annotations

import asyncio


def _facts(html, **kwargs):
    from services.prospecting.web_facts import extract_web_facts

    return extract_web_facts(html, **kwargs)


def test_title_e_meta_description():
    facts = _facts(
        '<html><head><title>Metalúrgica Ex  &amp; Cia</title>'
        '<meta name="description" content="Usinagem pesada.">'
        '</head></html>',
        url="https://exemplo.example/",
    )
    assert facts["page_title"] == "Metalúrgica Ex & Cia"
    assert facts["meta_description"] == "Usinagem pesada."


def test_ausencia_de_meta_vira_unknown_nao_falso():
    facts = _facts("<html><head><title>X</title></head></html>")
    assert facts["meta_description"] is None
    assert facts["meta_presence"] == "unknown"


def test_canonical_e_links_de_paginas():
    facts = _facts(
        '<html><head><link rel="canonical" href="https://exemplo.example/"></head>'
        '<body><a href="/contato">Contato</a><a href="/sobre-nos">Sobre</a>'
        '<a href="/servicos/usinagem">Serviços</a></body></html>',
        url="https://exemplo.example/",
    )
    assert facts["canonical_url"] == "https://exemplo.example/"
    assert facts["contact_page"] == "https://exemplo.example/contato"
    assert facts["about_page"] == "https://exemplo.example/sobre-nos"
    assert facts["services_page"] == "https://exemplo.example/servicos/usinagem"


def test_email_telefone_publicos_e_sociais():
    facts = _facts(
        '<html><body>contato@exemplo.example (11) 3333-0000 '
        '<a href="https://instagram.com/exemplo">ig</a></body></html>',
    )
    assert "contato@exemplo.example" in facts["public_emails"]
    assert facts["public_phones"]
    assert facts["social_links"]["instagram"] == "https://instagram.com/exemplo"


def test_html_malformado_nao_quebra_extracao():
    facts = _facts("<html><head><title>A<title><body><a href=/contato>X")
    assert facts["page_title"] == "A"
    assert facts["contact_page"] == "/contato"


def test_timeout_nao_vira_website_absent():
    from services.prospecting.web_facts import facts_from_fetch_result

    facts = facts_from_fetch_result(
        {"status": "failed", "reason": "timeout"}, url="https://x.example/"
    )
    assert facts["site_reachable"] == "unknown"
    assert "website_absent" not in facts


def test_fetch_ok_sem_title_mantem_unknown():
    from services.prospecting.web_facts import facts_from_fetch_result

    facts = facts_from_fetch_result(
        {"status": "ok", "text": "<html><body>oi</body></html>"},
        url="https://x.example/",
    )
    assert facts["site_reachable"] is True
    assert facts["page_title"] is None
