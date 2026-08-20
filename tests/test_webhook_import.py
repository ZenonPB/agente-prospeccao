"""Testes do importador de leads via webhook (n8n/Make/Zapier).

Cobrem os helpers puros (sanitização, place_id determinístico, aliases de
cabeçalho) e o fluxo com DB fake: fallback de cidade/estado para a campanha,
regressão do `source` inválido no Lead, contato só com nome e deduplicação
por site/CNPJ/place_id.
"""
from types import SimpleNamespace

from src.db.dependencies import get_db
from src.services.webhook_import_service import (
    clean_url,
    clean_cnpj,
    generate_place_id,
    normalize_header,
    normalize_import_website,
    import_leads_from_webhook,
)


# ---------- helpers puros ----------


def test_clean_url_forca_https():
    assert clean_url("firma.com.br") == "https://firma.com.br"
    assert clean_url("http://firma.com.br") == "http://firma.com.br"
    assert clean_url(" https://firma.com.br/x ") == "https://firma.com.br/x"
    assert clean_url(None) is None
    assert clean_url("  ") is None


def test_clean_cnpj_so_digitos():
    assert clean_cnpj("12.345.678/0001-95") == "12345678000195"
    assert clean_cnpj("12345678") is None  # CNPJ inválido (curto)
    assert clean_cnpj(None) is None


def test_generate_place_id_deterministico():
    a = generate_place_id("Padaria Estrela", "https://padaria.com", "12345678000195")
    b = generate_place_id("Padaria Estrela", "https://padaria.com", "12345678000195")
    c = generate_place_id("Padaria Estrela", "https://outro.com", "12345678000195")
    assert a == b
    assert a != c
    assert a.startswith("webhook_")


def test_normalize_header_aliases():
    assert normalize_header("Nome da Empresa") == "name"
    assert normalize_header("telefone") == "phone"
    assert normalize_header("whatsapp") == "whatsapp"
    assert normalize_header("documento") == "cnpj"
    assert normalize_header("e-mail") == "email"
    assert normalize_header("perfil_linkedin") == "linkedin"
    assert normalize_header("coluna desconhecida") == "coluna_desconhecida"


def test_normalize_import_website_anula_sem_site_proprio():
    assert normalize_import_website("canva.link/artigo") is None
    assert normalize_import_website("https://www.instagram.com/loja") is None
    assert normalize_import_website("firma.com.br") == "https://firma.com.br"


# ---------- fluxo com DB fake ----------


class _FakeQ:
    def __init__(self, first_result=None):
        self.first_result = first_result

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self.first_result


class _FakeDb:
    """DB fake por modelo: Campaign devolve a campanha; Lead devolve `existing`."""

    def __init__(self, campaign, existing_lead=None):
        self.campaign = campaign
        self.existing_lead = existing_lead
        self.added = []
        self.committed = 0

    def query(self, model):
        from src.db.models import Campaign, Lead
        if model is Campaign:
            return _FakeQ(self.campaign)
        if model is Lead:
            return _FakeQ(self.existing_lead)
        return _FakeQ(None)

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass

    def commit(self):
        self.committed += 1


def _campaign(**overrides):
    base = dict(
        id="c-1",
        organization_id="org-1",
        target_city=None,
        target_state=None,
        target_segment=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _added_leads(db):
    from src.db.models import Lead
    return [o for o in db.added if isinstance(o, Lead)]


def _added_contacts(db):
    from src.db.models import Contact
    return [o for o in db.added if isinstance(o, Contact)]


def test_importa_lead_com_fallback_de_cidade_estado_da_campanha():
    db = _FakeDb(_campaign(target_city="São Carlos", target_state="SP"))
    out = import_leads_from_webhook(
        db,
        campaign_id="c-1",
        leads_data=[{"name": "Usinagem Silva", "website": "usinagemsilva.com.br"}],
    )

    assert out["imported_count"] == 1
    assert out["error_count"] == 0
    lead = _added_leads(db)[0]
    assert lead.city == "São Carlos"
    assert lead.state == "SP"
    assert lead.normalized_domain == "usinagemsilva.com.br"
    assert lead.campaign_id == "c-1"


def test_contato_so_e_criado_quando_ha_nome():
    db = _FakeDb(_campaign())
    out = import_leads_from_webhook(
        db,
        campaign_id="c-1",
        leads_data=[
            # E-mail sem decisor: não vira contato fantasma (contacts.name é NOT NULL).
            {"name": "Empresa A", "email": "contato@empresa.com.br"},
            # Com decisor: contato válido com fonte webhook.
            {
                "name": "Empresa B",
                "contact_name": "Ana Souza",
                "email": "ana@empresa.com.br",
                "whatsapp": "16999999999",
            },
        ],
    )

    assert out["imported_count"] == 2
    assert out["error_count"] == 0
    contacts = _added_contacts(db)
    assert len(contacts) == 1
    assert contacts[0].name == "Ana Souza"
    assert contacts[0].source == "webhook"
    assert contacts[0].email == "ana@empresa.com.br"
    assert contacts[0].phone == "16999999999"


def test_nome_obrigatorio_por_linha():
    db = _FakeDb(_campaign())
    out = import_leads_from_webhook(
        db,
        campaign_id="c-1",
        leads_data=[{"name": "Empresa A"}, {"website": "semsite.com.br"}],
    )

    assert out["imported_count"] == 1
    assert out["error_count"] == 1
    assert out["errors"][0]["row"] == 2
    assert out["errors"][0]["message"] == "Informe o nome da empresa"


def test_duplicata_por_website_nao_importa_de_novo():
    existing = SimpleNamespace(id="L1", company_name="Usinagem Silva")
    db = _FakeDb(_campaign(), existing_lead=existing)
    out = import_leads_from_webhook(
        db,
        campaign_id="c-1",
        leads_data=[{"name": "Usinagem Silva", "website": "usinagemsilva.com.br"}],
    )

    assert out["duplicate_count"] == 1
    assert out["imported_count"] == 0
    assert out["errors"][0]["field"] == "duplicate"
    assert out["errors"][0]["existing_lead_id"] == "L1"


def test_duplicata_por_cnpj_nao_importa_de_novo():
    existing = SimpleNamespace(id="L2", company_name="Outra Razão")
    db = _FakeDb(_campaign(), existing_lead=existing)
    out = import_leads_from_webhook(
        db,
        campaign_id="c-1",
        leads_data=[{"name": "Nome Fantasia", "cnpj": "12.345.678/0001-95"}],
    )

    assert out["duplicate_count"] == 1
    assert out["imported_count"] == 0


def test_sem_cidade_em_linha_nem_campanha_nao_quebra_o_fluxo():
    # Igual ao CSV: `city` cai no `target_city` da campanha; sem ele, o valor
    # fica vazio e o DB (real) decide. A importação não pode lançar por linha.
    db = _FakeDb(_campaign())
    out = import_leads_from_webhook(
        db,
        campaign_id="c-1",
        leads_data=[{"name": "Indústria X"}],
    )
    assert out["imported_count"] == 1
    assert out["error_count"] == 0
    assert _added_leads(db)[0].city is None


def test_campanha_inexistente_levanta_valueerror():
    import pytest

    class _EmptyDb:
        def query(self, model):
            return _FakeQ(None)

    with pytest.raises(ValueError):
        import_leads_from_webhook(
            _EmptyDb(), campaign_id="nao-existe", leads_data=[{"name": "X"}],
        )


# ---------- rota pública (HTTP) ----------


def test_webhook_import_via_http_sem_segredo_levanta_401(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import src.routes.webhooks as webhooks_module

    monkeypatch.setattr(webhooks_module.settings, "EMAIL_WEBHOOK_SECRET", "segredo-teste")

    app = FastAPI()
    app.include_router(webhooks_module.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: _FakeDb(_campaign())
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.post(
        "/api/webhooks/import",
        json={"campaign_id": "c-1", "leads": [{"name": "Empresa A"}]},
    )
    assert resp.status_code == 401


def test_webhook_import_via_http_com_segredo_importa_lead(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import src.routes.webhooks as webhooks_module

    monkeypatch.setattr(webhooks_module.settings, "EMAIL_WEBHOOK_SECRET", "segredo-teste")

    app = FastAPI()
    app.include_router(webhooks_module.router, prefix="/api")
    db = _FakeDb(_campaign(target_city="São Carlos"))
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.post(
        "/api/webhooks/import",
        headers={"X-Webhook-Secret": "segredo-teste"},
        json={
            "campaign_id": "c-1",
            "leads": [
                {
                    "name": "Usinagem Silva",
                    "website": "usinagemsilva.com.br",
                    "contact_name": "Ana Souza",
                    "email": "ana@usinagemsilva.com.br",
                }
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["imported_count"] == 1
    lead = _added_leads(db)[0]
    assert lead.city == "São Carlos"
    assert _added_contacts(db)[0].name == "Ana Souza"