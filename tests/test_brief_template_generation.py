"""Regressão do preview do meio agente (POST /api/campaigns/from-brief).

Vertical nova (rota GENERATE_NEW) deve gerar o template de critérios já no
preview — e não exibir "Genérico" e adiar a geração para o pipeline.
"""
from types import SimpleNamespace

from starlette.requests import Request

import src.routes.campaigns as campaigns_routes
from src.routes.campaigns import BriefCampaignRequest, create_campaign_from_brief


def _request():
    # App com limiter "vazio" → o decorador slowapi passa direto.
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/campaigns/from-brief",
        "headers": [],
        "query_string": b"",
        "app": SimpleNamespace(state=SimpleNamespace(limiter=None)),
    }
    return Request(scope)


class _FakeQuery:
    def __init__(self, row):
        self._row = row

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._row


class _FakeDB:
    def __init__(self, row=None):
        self._row = row
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def query(self, *a, **k):
        return _FakeQuery(self._row)


def _patch_chain(monkeypatch, suggestion, route_result, generate):
    """Intercepta os serviços dos workers usados pelo endpoint."""
    monkeypatch.setattr(
        "services.provider_client.quota_ok", lambda db, org, key: True
    )

    class FakeSecretService:
        @staticmethod
        async def resolve_all(db, org_id):
            return {"GROQ_API_KEY": "key-teste"}

    monkeypatch.setattr(
        "services.secret_service.SecretService", FakeSecretService
    )

    class FakeBriefService:
        def __init__(self, api_key=None):
            pass

        async def interpret(self, brief, db=None, organization_id=None):
            return suggestion

    monkeypatch.setattr(
        "services.campaign_brief_service.CampaignBriefService", FakeBriefService
    )

    async def fake_route(db, **kwargs):
        return route_result

    monkeypatch.setattr(
        "services.template_router.route_scoring_template", fake_route
    )

    class FakeGenerationService:
        calls = []

        def __init__(self, api_key=None):
            pass

        async def generate(self, db, target_service="", target_segment="", organization_id=None):
            FakeGenerationService.calls.append(target_service)
            return generate(db, target_service, target_segment, organization_id)

    monkeypatch.setattr(
        "services.template_generation_service.TemplateGenerationService",
        FakeGenerationService,
    )


def _tmpl_row():
    return SimpleNamespace(
        id="tmpl-1",
        service_label="Landing Pages para Clínicas",
        is_active=True,
    )


def test_generate_new_gera_template_no_preview(monkeypatch):
    suggestion = {
        "target_service": "Landing pages",
        "target_segment": "Clínicas de fisioterapia",
    }
    route_result = {
        "template": {"service_label": "Genérico"},
        "route": "GENERATE_NEW",
        "matched_label": "Genérico",
    }
    _patch_chain(
        monkeypatch, suggestion, route_result,
        lambda db, s, seg, org: {"service_label": "Landing Pages para Clínicas"},
    )
    db = _FakeDB(row=_tmpl_row())

    import asyncio
    result = asyncio.run(create_campaign_from_brief(
        request=_request(),
        body=BriefCampaignRequest(brief="quero vender landing pages"),
        db=db,
        _user=SimpleNamespace(id="u1"),
        _org=SimpleNamespace(id="org1"),
    ))

    assert result["scoring_template_label"] == "Landing Pages para Clínicas"
    assert result["scoring_template_id"] == "tmpl-1"
    assert result["template_route"] == "MATCHED"
    assert db.commits == 1


def test_falha_na_geracao_mantem_fallback_generico(monkeypatch):
    suggestion = {
        "target_service": "Manutenção de elevadores",
        "target_segment": "Condomínios",
    }
    route_result = {
        "template": {"service_label": "Genérico"},
        "route": "GENERATE_NEW",
        "matched_label": "Genérico",
    }

    def boom(db, s, seg, org):
        raise RuntimeError("Groq indisponível")

    _patch_chain(monkeypatch, suggestion, route_result, boom)
    db = _FakeDB(row=SimpleNamespace(
        id="tmpl-generico", service_label="Genérico", is_active=True,
    ))

    import asyncio
    result = asyncio.run(create_campaign_from_brief(
        request=_request(),
        body=BriefCampaignRequest(brief="manutenção de elevadores"),
        db=db,
        _user=SimpleNamespace(id="u1"),
        _org=SimpleNamespace(id="org1"),
    ))

    assert result["scoring_template_label"] == "Genérico"
    assert result["scoring_template_id"] == "tmpl-generico"
    assert result["template_route"] == "GENERATE_NEW"
    assert db.rollbacks == 1
