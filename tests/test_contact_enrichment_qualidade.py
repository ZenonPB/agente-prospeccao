"""Testes das melhorias de contatos (nomes/emails de decisores).

Cobre:
- B3: `_extract_emails_from_html` NÃO captura URLs/CDN como e-mail;
- B4: heurística de e-mail só roda para nome de pessoa (nunca nome da empresa),
      e o fallback genérico não usa o nome da empresa como decisor;
- B1: parsing do Hunter domain-search (nomes + cargos + e-mails reais);
- B2: descoberta reversa de CNPJ por nome (busca passiva) + helpers.
"""
import asyncio

from services.contact_enrichment_service import (
    ContactEnrichmentService,
    _extract_emails_from_html,
    _looks_like_person_name,
    _role_from_position,
    extract_cnpj_candidates,
    parse_hunter_domain_emails,
)
from database.models import Contact, ContactRole, Lead


# --------------------------------------------------------------------------- #
# B3 — extração de e-mail não captura URL/CDN
# --------------------------------------------------------------------------- #
def test_extract_emails_ignora_cdn_e_urls():
    html = (
        '<script src="//unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>'
        "<a href='mailto:contato@bluefit.com.br'>x</a>"
    )
    emails = _extract_emails_from_html(html)
    assert "contato@bluefit.com.br" in emails
    assert not any("leaflet" in e or "unpkg" in e for e in emails)
    assert not any("/" in e.split("@")[0] for e in emails)


def test_extract_emails_ignora_cdn_jsdelivr():
    html = '<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.min.js"></script>'
    assert _extract_emails_from_html(html) == []


def test_extract_emails_mantem_email_valido_ao_lado_de_cdn():
    html = (
        '<script src="//unpkg.com/leaflet@1.7.1"></script>'
        "<p>mariana&#64;exemplo.com.br</p>"
    )
    emails = _extract_emails_from_html(html)
    assert "mariana@exemplo.com.br" in emails


# --------------------------------------------------------------------------- #
# B4 — heurística honesta (só para nome de pessoa)
# --------------------------------------------------------------------------- #
def test_looks_like_person_name():
    assert _looks_like_person_name("João Silva", "Academia Max Gym") is True
    assert _looks_like_person_name("Academia Max Gym", "Academia Max Gym") is False
    assert _looks_like_person_name("Decisor", "Academia Max Gym") is False
    assert _looks_like_person_name("", "Academia Max Gym") is False
    assert _looks_like_person_name("Ultra Academia São Carlos", "Ultra Academia São Carlos") is False


def _make_contact(name="João Silva", source="cnpj_receita"):
    return Contact(
        lead_id=None,
        name=name,
        role=ContactRole.SOCIO,
        role_label="Sócio",
        confidence=70,
        is_primary=True,
        source=source,
        raw_data={},
    )


def _make_lead(website="https://exemplo.com.br", company="Exemplo Ltda"):
    return Lead(company_name=company, website=website, city="Araraquara", state="SP")


class _FakeClient:
    pass


def test_enrich_email_nao_gera_heuristica_do_nome_da_empresa():
    async def run():
        svc = ContactEnrichmentService()
        lead = _make_lead(website="https://maxgym.com.br", company="Academia Max Gym")
        contact = _make_contact(name="Academia Max Gym")
        await svc._enrich_email(_FakeClient(), contact, lead)
        return contact

    contact = asyncio.run(run())
    # Sem email do site/nome real → NÃO inventa email do nome da empresa.
    assert contact.email is None
    assert "email_source" not in (contact.raw_data or {})


def test_enrich_email_heuristica_so_para_nome_de_pessoa():
    async def run():
        svc = ContactEnrichmentService()
        lead = _make_lead(website="https://exemplo.com.br", company="Exemplo Ltda")
        contact = _make_contact(name="Mariana Souza")
        await svc._enrich_email(_FakeClient(), contact, lead)
        return contact

    contact = asyncio.run(run())
    assert contact.email == "mariana.souza@exemplo.com.br"
    assert contact.raw_data["email_source"] == "heuristic"


# --------------------------------------------------------------------------- #
# B1 — Hunter domain-search (parsing puro)
# --------------------------------------------------------------------------- #
def test_role_from_position():
    assert _role_from_position("Diretor Comercial") == ContactRole.DIRETOR
    assert _role_from_position("CEO") == ContactRole.CEO
    assert _role_from_position("Sócio Administrador") == ContactRole.SOCIO
    assert _role_from_position("Presidente") == ContactRole.CEO
    assert _role_from_position("Consultora de marketing") == ContactRole.OUTRO
    assert _role_from_position("") == ContactRole.OUTRO


def test_parse_hunter_domain_emails():
    payload = {
        "data": {
            "emails": [
                {
                    "value": "joao@exemplo.com.br",
                    "type": "personal",
                    "first_name": "João",
                    "last_name": "Silva",
                    "position": "Diretor Comercial",
                    "confidence": 95,
                },
                {
                    "value": "contato@exemplo.com.br",
                    "type": "generic",
                    "first_name": "",
                    "last_name": "",
                    "position": "",
                    "confidence": 90,
                },
                {"value": "naoemail", "type": "personal", "first_name": "", "last_name": "", "position": "", "confidence": 10},
            ]
        }
    }
    people = parse_hunter_domain_emails(payload)
    # Só e-mails pessoais válidos entram; e-mail genérico e inválido são ignorados.
    assert len(people) == 1
    p = people[0]
    assert p["name"] == "João Silva"
    assert p["email"] == "joao@exemplo.com.br"
    assert p["role"] is ContactRole.DIRETOR
    assert p["role_label"] == "Diretor Comercial"
    assert p["confidence"] == 95
    assert p["is_primary"] is True


# --------------------------------------------------------------------------- #
# B2 — descoberta reversa de CNPJ (helpers puros)
# --------------------------------------------------------------------------- #
def test_extract_cnpj_candidates():
    text = (
        "CNPJ: 35.481.049/0001-35 — Academia Max Gym.<br>"
        "Outro: 12345678000199"
    )
    found = extract_cnpj_candidates(text)
    assert "35481049000135" in found
    assert "12345678000199" in found


def test_extract_cnpj_candidates_vazio():
    assert extract_cnpj_candidates("sem cnpj aqui") == []