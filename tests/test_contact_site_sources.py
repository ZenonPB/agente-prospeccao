"""Testes das novas fontes de contato (roadmap-vendas 4.7).

Cobrem as funções puras de extração/desofuscação e a precedência de e-mail
(Hunter → site → busca → CNPJ → heurística) sem rede e sem banco.
"""
import asyncio

from services.contact_enrichment_service import (
    ContactEnrichmentService,
    _extract_emails_from_html,
    _extract_phone_from_html,
    _pick_email_for_name,
    _pick_site_email,
)
from database.models import Contact, ContactRole
from database.models import Lead


# --------------------------------------------------------------------------- #
# Extração de HTML (página de contato)
# --------------------------------------------------------------------------- #
def test_extract_emails_from_mailto_and_plain():
    html = """
    <a href="mailto:comercial@exemplo.com.br">Fale conosco</a>
    <p>Vendas: vendas@exemplo.com.br — suporte@sac.com.br</p>
    """
    emails = _extract_emails_from_html(html)
    assert "comercial@exemplo.com.br" in emails
    assert "vendas@exemplo.com.br" in emails
    assert "suporte@sac.com.br" in emails


def test_extract_emails_desofuscado():
    html = """
    contato@exemplo [dot] com.br
    mariana [at] exemplo.com.br
    financeiro&#64;exemplo.com.br &#46;com.br
    """
    emails = _extract_emails_from_html(html)
    assert "contato@exemplo.com.br" in emails
    assert "mariana@exemplo.com.br" in emails
    assert "financeiro@exemplo.com.br" in emails


def test_extract_emails_invalid_ou_vazio():
    assert _extract_emails_from_html(None) == []
    assert _extract_emails_from_html("<p>sem email aqui</p>") == []
    # Sem arroba válido / local part inválido.
    assert _extract_emails_from_html("mailto:nao-email") == []


def test_extract_emails_deduplica():
    html = "<a href='mailto:a@b.com'>x</a><p>a@b.com</p>"
    emails = _extract_emails_from_html(html)
    assert emails.count("a@b.com") == 1


def test_extract_phone_from_html():
    html = "Tel: (16) 3372-1234 ou 16 99711-2233 e fixo 3372-4567"
    phones = _extract_phone_from_html(html)
    assert "1633721234" in phones
    assert "16997112233" in phones


# --------------------------------------------------------------------------- #
# Seleção do melhor e-mail do site
# --------------------------------------------------------------------------- #
def test_pick_site_email_prefere_dominio_e_nao_generico():
    emails = ["comercial@outro.com.br", "mariana@exemplo.com.br"]
    pick, conf = _pick_site_email(emails, "exemplo.com.br")
    assert pick == "mariana@exemplo.com.br"
    assert conf == 75


def test_pick_site_email_generico_cap_69():
    pick, conf = _pick_site_email(["comercial@exemplo.com.br"], "exemplo.com.br")
    assert pick == "comercial@exemplo.com.br"
    assert conf == 69


def test_pick_site_email_sem_dominio_match():
    pick, conf = _pick_site_email(["joao@gmail.com"], "exemplo.com.br")
    assert pick == "joao@gmail.com"
    assert conf == 69


def test_pick_site_email_vazio():
    assert _pick_site_email([], "exemplo.com.br") == (None, 0)


# --------------------------------------------------------------------------- #
# Seleção de e-mail por nome (busca)
# --------------------------------------------------------------------------- #
def test_pick_email_for_name_por_overlap():
    candidates = ["contato@grande.com.br", "joao.silva@exemplo.com.br"]
    pick = _pick_email_for_name(candidates, "João Silva")
    assert pick == "joao.silva@exemplo.com.br"


def test_pick_email_for_name_sem_overlap():
    assert _pick_email_for_name(["admin@site.com"], "Maria Souza") is None


# --------------------------------------------------------------------------- #
# `_apply_email` (proveniência) e precedência em `_enrich_email`
# --------------------------------------------------------------------------- #
def _make_contact(name="João Silva"):
    return Contact(
        lead_id=None,
        name=name,
        role=ContactRole.SOCIO,
        role_label="Sócio",
        confidence=70,
        is_primary=True,
        source="cnpj_receita:brasilapi",
        raw_data={},
    )


def _make_lead(website="https://exemplo.com.br", company="Exemplo Ltda"):
    return Lead(
        company_name=company,
        website=website,
        city="Araraquara",
        state="SP",
    )


class _FakeClient:
    """Suficiente para os branches sem rede de `_enrich_email`."""


def test_apply_email_grava_proveniencia():
    contact = _make_contact()
    ContactEnrichmentService()._apply_email(contact, "mariana@exemplo.com.br", "site", 75)
    assert contact.email == "mariana@exemplo.com.br"
    assert contact.raw_data["email_source"] == "site"
    assert contact.source.endswith(":site")


def test_enrich_email_site_vem_antes_de_heuristica():
    async def run():
        svc = ContactEnrichmentService()
        contact = _make_contact()
        lead = _make_lead()
        await svc._enrich_email(
            _FakeClient(), contact, lead,
            site_emails=["comercial@exemplo.com.br"],
            site_phones=["1633721234"],
        )
        return contact

    contact = asyncio.run(run())
    assert contact.email == "comercial@exemplo.com.br"
    assert contact.raw_data["email_source"] == "site"
    assert contact.phone == "1633721234"
    assert contact.raw_data["phone_source"] == "site"


def test_enrich_email_cnpj_vem_antes_de_heuristica():
    async def run():
        svc = ContactEnrichmentService()
        contact = _make_contact()
        contact.raw_data = {"company_email": "contato@exemplo.com.br"}
        lead = _make_lead()
        await svc._enrich_email(_FakeClient(), contact, lead)
        return contact

    contact = asyncio.run(run())
    assert contact.email == "contato@exemplo.com.br"
    assert contact.raw_data["email_source"] == "cnpj"


def test_enrich_email_heuristica_ultimo_recurso():
    async def run():
        svc = ContactEnrichmentService()
        contact = _make_contact(name="João Silva")
        lead = _make_lead()
        await svc._enrich_email(_FakeClient(), contact, lead)
        return contact

    contact = asyncio.run(run())
    assert contact.email == "joao.silva@exemplo.com.br"
    assert contact.raw_data["email_source"] == "heuristic"
    assert contact.raw_data["email_verified"] is False