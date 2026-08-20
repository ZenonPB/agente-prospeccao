"""Gerenciador de vertentes.

Cobre: permissão (criar/editar/gerar/apagar apenas MANAGER/owner/admin),
duplicação via `source_template_id`, geração por IA como rascunho
(`is_generated=True`, inativa), remoção de vertentes da org (globais protegidas
e em uso protegidas).
"""
import asyncio
from types import SimpleNamespace
from typing import Dict, Optional

import pytest
from fastapi import HTTPException

from src.auth.dependencies import require_manager
from src.db.models import Campaign, CampaignScoringTemplate, OrganizationRole, SalesRole
from src.routes.scoring_templates import (
    CreateScoringTemplateRequest,
    GenerateScoringTemplateRequest,
    create_scoring_template,
    delete_scoring_template,
    generate_scoring_template,
    patch_scoring_template,
)


# ---------- utilidades ----------

def _request():
    from starlette.requests import Request
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/scoring-templates/generate",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 50000),
    })

class _FakeQ:
    """First/Count falsificados, consumindo resultados em ordem."""

    def __init__(self, first_results=None, count_value=0):
        self.results = list(first_results or [])
        self.count_value = count_value

    def filter(self, *_a, **_k):
        return self

    def first(self):
        if self.results:
            return self.results.pop(0)
        return None

    def count(self):
        return self.count_value


class _FakeDb:
    def __init__(self, by_model: Optional[Dict] = None):
        self.by_model = by_model or {}
        self.added = None
        self.deleted = None

    def query(self, model):
        return self.by_model.get(model, _FakeQ())

    def add(self, obj):
        self.added = obj

    def commit(self):
        pass

    def refresh(self, _obj):
        pass

    def delete(self, obj):
        self.deleted = obj


def _manager(*, role=OrganizationRole.OWNER, sales_role=None):
    return SimpleNamespace(id="u", role=role, sales_role=sales_role)


def _org(id="org-1"):
    return SimpleNamespace(id=id)


def _signal(label, weight="medium", description=""):
    return {"label": label, "description": description, "weight_hint": weight}


def _seed(organization_id=None, label="Engenharia Mecânica"):
    return SimpleNamespace(
        id="seed-1",
        service_label=label,
        positive_signals=[_signal("Porte industrial", "high")],
        negative_signals=[_signal("Serviços residenciais", "low")],
        context_signals=[_signal("Segmento")],
        requires_technical_report=False,
        requires_business_data=True,
        enrichment_steps=["cnpj_receita", "business_social"],
        cadence_schedule=[0, 7, 30, 60],
        extra_instructions="Foco em manufatura",
        playbook={"hooks": ["Olá, fábrica?"]},
        is_generated=False,
        is_active=True,
        organization_id=organization_id,
        created_at=None,
        updated_at=None,
    )


# ---------- permissão ----------

def test_consultor_e_analyst_nao_gerenciam_vertentes():
    for role, sales_role in (
        (OrganizationRole.MEMBER, SalesRole.CONSULTOR),
        (OrganizationRole.MEMBER, SalesRole.ANALYST),
    ):
        member = SimpleNamespace(role=role, sales_role=sales_role)
        with pytest.raises(HTTPException) as exc:
            require_manager()(member=member)
        assert exc.value.status_code == 403
        assert "Papel de venda insuficiente" in exc.value.detail


def test_manager_owner_admin_gerenciam_vertentes():
    ok_cases = [
        (OrganizationRole.MEMBER, SalesRole.MANAGER),
        (OrganizationRole.OWNER, None),
        (OrganizationRole.ADMIN, None),
    ]
    for role, sales_role in ok_cases:
        member = require_manager()(member=SimpleNamespace(role=role, sales_role=sales_role))
        assert member is not None


# ---------- duplicar via source_template_id ----------

def test_duplicar_vertente_global_cria_copia_na_org():
    db = _FakeDb({CampaignScoringTemplate: _FakeQ(first_results=[_seed(organization_id=None)])})
    body = CreateScoringTemplateRequest(
        service_label="Engenharia Mecânica (nosso ICP)",
        source_template_id="seed-1",
    )
    out = create_scoring_template(
        body, db,
        _user=SimpleNamespace(id="u"),
        org=_org(),
        member=_manager(),
    )
    created = db.added
    assert created is not None
    assert created.organization_id == "org-1"
    assert created.service_label == "Engenharia Mecânica (nosso ICP)"
    assert created.is_active is True
    assert created.positive_signals[0]["label"] == "Porte industrial"
    assert created.cadence_schedule == [0, 7, 30, 60]
    assert created.playbook["hooks"] == ["Olá, fábrica?"]
    assert out["positive_signals"][0]["label"] == "Porte industrial"


def test_duplicar_vertente_inexistente_404():
    db = _FakeDb({CampaignScoringTemplate: _FakeQ(first_results=[None])})
    body = CreateScoringTemplateRequest(
        service_label="Qualquer", source_template_id="nao-existe",
    )
    with pytest.raises(HTTPException) as exc:
        create_scoring_template(
            body, db,
            _user=SimpleNamespace(id="u"),
            org=_org(),
            member=_manager(),
        )
    assert exc.value.status_code == 404


def test_duplicar_com_body_explicito_tem_precedencia():
    db = _FakeDb({CampaignScoringTemplate: _FakeQ(first_results=[_seed()])})
    body = CreateScoringTemplateRequest(
        service_label="Engenharia (custom)",
        source_template_id="seed-1",
        cadence_schedule=[0, 3, 7, 14],
    )
    create_scoring_template(
        body, db,
        _user=SimpleNamespace(id="u"),
        org=_org(),
        member=_manager(),
    )
    assert db.added.cadence_schedule == [0, 3, 7, 14]
    assert db.added.positive_signals[0]["label"] == "Porte industrial"


def test_duplicar_label_duplicado_na_org_409():
    seed = _seed(organization_id="org-1")
    db = _FakeDb({
        # 1ª chamada `.first()` (busca da origem) → seed; 2ª (conflito de
        # label) → seed de novo, pois o label já existe na org.
        CampaignScoringTemplate: _FakeQ(first_results=[seed, seed]),
    })
    body = CreateScoringTemplateRequest(
        service_label="Engenharia Mecânica",
        source_template_id="seed-1",
    )
    with pytest.raises(HTTPException) as exc:
        create_scoring_template(
            body, db,
            _user=SimpleNamespace(id="u"),
            org=_org(),
            member=_manager(),
        )
    assert exc.value.status_code == 409


# ---------- gerar por IA (rascunho) ----------

PIPELINE_APA = "services.provider_client.quota_ok"
PIPELINE_SECRETS = "services.secret_service.SecretService"
PIPELINE_SVC = "services.template_generation_service.TemplateGenerationService"


async def _ok_generate(*_a, **_k):
    return {
        "service_label": "Manutenção de compressores para indústrias",
        "requires_technical_report": False,
        "requires_business_data": True,
        "enrichment_steps": ["cnpj_receita", "business_social"],
        "cadence_schedule": None,
        "positive_signals": [_signal("Fábrica com máquinas rotativas", "high")],
        "negative_signals": [_signal("Empresa de serviços", "medium")],
        "context_signals": [_signal("Setor industrial")],
        "extra_instructions": "Priorize porte industrial.",
    }


async def _ok_resolve_all(*_a, **_k):
    return {}


def test_generate_persiste_rascunho_inativo(monkeypatch):
    monkeypatch.setattr(PIPELINE_APA, lambda *a, **k: True)
    monkeypatch.setattr(PIPELINE_SECRETS + ".resolve_all", _ok_resolve_all)
    monkeypatch.setattr(PIPELINE_SVC + ".build_draft", _ok_generate)

    db = _FakeDb({CampaignScoringTemplate: _FakeQ(first_results=[None])})
    body = GenerateScoringTemplateRequest(
        service="manutenção de compressores",
        segment="indústrias",
        description="empresas com compressores parados",
    )
    out = asyncio.run(generate_scoring_template(
        _request(), body, db,
        _user=SimpleNamespace(id="u"),
        org=_org(),
        member=_manager(),
    ))
    created = db.added
    assert created is not None
    assert created.is_generated is True
    assert created.is_active is False
    assert created.organization_id == "org-1"
    assert created.playbook == {}
    assert out["is_generated"] is True
    assert out["is_active"] is False


def test_generate_sem_quota_429(monkeypatch):
    monkeypatch.setattr(PIPELINE_APA, lambda *a, **k: False)
    db = _FakeDb()
    body = GenerateScoringTemplateRequest(service="sites")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(generate_scoring_template(
            _request(), body, db,
            _user=SimpleNamespace(id="u"),
            org=_org(),
            member=_manager(),
        ))
    assert exc.value.status_code == 429


def test_generate_falha_llm_502(monkeypatch):
    monkeypatch.setattr(PIPELINE_APA, lambda *a, **k: True)
    monkeypatch.setattr(PIPELINE_SECRETS + ".resolve_all", _ok_resolve_all)

    async def _fail(*_a, **_k):
        return None

    monkeypatch.setattr(PIPELINE_SVC + ".build_draft", _fail)
    db = _FakeDb()
    body = GenerateScoringTemplateRequest(service="sites")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(generate_scoring_template(
            _request(), body, db,
            _user=SimpleNamespace(id="u"),
            org=_org(),
            member=_manager(),
        ))
    assert exc.value.status_code == 502


# ---------- apagar ----------

def test_delete_vertente_da_org_sem_uso():
    tmpl = _seed(organization_id="org-1", label="Minha vertente")
    db = _FakeDb({
        CampaignScoringTemplate: _FakeQ(first_results=[tmpl]),
        Campaign: _FakeQ(count_value=0),
    })
    out = delete_scoring_template(
        "seed-1", db,
        _user=SimpleNamespace(id="u"),
        org=_org(),
        member=_manager(),
    )
    assert out["deleted"] is True
    assert db.deleted is tmpl


def test_delete_vertente_em_uso_409():
    tmpl = _seed(organization_id="org-1")
    db = _FakeDb({
        CampaignScoringTemplate: _FakeQ(first_results=[tmpl]),
        Campaign: _FakeQ(count_value=2),
    })
    with pytest.raises(HTTPException) as exc:
        delete_scoring_template(
            "seed-1", db,
            _user=SimpleNamespace(id="u"),
            org=_org(),
            member=_manager(),
        )
    assert exc.value.status_code == 409


def test_delete_vertente_global_ou_de_outra_org_404():
    # O DELETE só enxerga vertentes da própria org — global ou de outra org
    # simplesmente não aparecem na busca (first() → None) → 404.
    db = _FakeDb({CampaignScoringTemplate: _FakeQ(first_results=[None])})
    with pytest.raises(HTTPException) as exc:
        delete_scoring_template(
            "seed-1", db,
            _user=SimpleNamespace(id="u"),
            org=_org(),
            member=_manager(),
        )
    assert exc.value.status_code == 404


def test_patch_renomear_verifica_conflito():
    current = _seed(organization_id="org-1", label="Antiga")
    current.id = "mine-1"
    db = _FakeDb({
        CampaignScoringTemplate: _FakeQ(
            first_results=[current, _seed(organization_id="org-1", label="Outra")],
        ),
    })
    from src.routes.scoring_templates import PatchScoringTemplateRequest
    body = PatchScoringTemplateRequest(service_label="Outra")
    with pytest.raises(HTTPException) as exc:
        patch_scoring_template(
            "mine-1", body, db,
            _user=SimpleNamespace(id="u"),
            org=_org(),
            member=_manager(),
        )
    assert exc.value.status_code == 409

    # Sem conflito: o segundo `.first()` devolve None e a renomeação passa.
    db2 = _FakeDb({
        CampaignScoringTemplate: _FakeQ(first_results=[current, None]),
    })
    out = patch_scoring_template(
        "mine-1", body, db2,
        _user=SimpleNamespace(id="u"),
        org=_org(),
        member=_manager(),
    )
    assert out["service_label"] == "Outra"