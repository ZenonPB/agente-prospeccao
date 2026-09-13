"""Isolamento tenant de vertentes (`CampaignScoringTemplate`).

Negativo obrigatório da Fase A: uma vertente privada do workspace A NUNCA
pode ser listada, resolvida, usada, editada ou duplicada pelo workspace B.
Tentativa direta por ID falha fechada (404).

Duas camadas:
- pura (sempre roda): visibilidade global/própria/estrangeira;
- banco real (exige `E2E_DATABASE_URL`, pulada sem banco como o E2E de
  outreach): roteamento exact/fuzzy/explícito/LLM + rotas da API.
"""
import asyncio
import os
import uuid
from types import SimpleNamespace

import pytest

from services.template_router import (
    ROUTE_GENERATE_NEW,
    normalize_key,
    route_scoring_template,
)

E2E_DB_URL = os.environ.get("E2E_DATABASE_URL")

if E2E_DB_URL:
    os.environ["DATABASE_URL"] = E2E_DB_URL
    os.environ["ENVIRONMENT"] = "test"


# ---------- camada pura: regra de visibilidade ----------

def _visible(organization_id, org_id) -> bool:
    """Espelha a regra esperada: global (NULL) ou da própria org."""
    if organization_id is None:
        return True
    return str(organization_id) == str(org_id)


def test_vertente_global_visivel_para_qualquer_org():
    assert _visible(None, "org-b") is True


def test_vertente_propria_visivel():
    assert _visible("org-a", "org-a") is True


def test_vertente_privada_de_outra_org_invisivel():
    assert _visible("org-a", "org-b") is False


def test_normalize_key_apoia_match_sem_vazar():
    assert normalize_key("Clínicas de Psicologia") == "clinicas de psicologia"


# ---------- camada com banco real ----------

def _unique_label(prefix: str) -> str:
    return f"{prefix} Isolamento {uuid.uuid4().hex[:8]}"


@pytest.fixture()
def tenant_pair():
    """Duas orgs + vertente privada de A. Limpa tudo ao final."""
    if not E2E_DB_URL:
        pytest.skip("E2E_DATABASE_URL não definido")
    from database.models import CampaignScoringTemplate, Organization
    from database.session import SessionLocal

    db = SessionLocal()
    created_template_ids = []
    created_org_ids = []
    try:
        org_a = Organization(name="Org A Isolamento", slug=f"org-a-iso-{uuid.uuid4().hex[:8]}")
        org_b = Organization(name="Org B Isolamento", slug=f"org-b-iso-{uuid.uuid4().hex[:8]}")
        db.add_all([org_a, org_b])
        db.flush()
        created_org_ids = [org_a.id, org_b.id]

        label_a = _unique_label("Vertente Privada A")
        tmpl_a = CampaignScoringTemplate(
            service_label=label_a,
            positive_signals=[],
            negative_signals=[],
            context_signals=[],
            is_active=True,
            organization_id=org_a.id,
        )
        db.add(tmpl_a)
        db.flush()
        created_template_ids.append(tmpl_a.id)
        db.commit()

        yield SimpleNamespace(
            db_url=E2E_DB_URL,
            org_a_id=str(org_a.id),
            org_b_id=str(org_b.id),
            label_a=label_a,
            template_a_id=str(tmpl_a.id),
        )
    finally:
        try:
            if created_template_ids:
                db.query(CampaignScoringTemplate).filter(
                    CampaignScoringTemplate.id.in_(created_template_ids)
                ).delete(synchronize_session=False)
            if created_org_ids:
                db.query(Organization).filter(
                    Organization.id.in_(created_org_ids)
                ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


def _fresh_db():
    from database.session import SessionLocal

    return SessionLocal()


def _stub_llm(monkeypatch, seen):
    async def _fake_classify(query, labels, api_key=None, db=None, organization_id=None):
        seen.append(list(labels))
        return ROUTE_GENERATE_NEW, ""

    monkeypatch.setattr("services.template_router._classify_llm", _fake_classify)


@pytest.mark.skipif(not E2E_DB_URL, reason="E2E_DATABASE_URL não definido")
def test_controle_org_dona_resolve_propria_vertente(tenant_pair):
    """Prova que o cenário não é vazio: A resolve a própria vertente."""
    db = _fresh_db()
    try:
        result = asyncio.run(
            route_scoring_template(
                db,
                target_service=tenant_pair.label_a,
                explicit_template_id=None,
                organization_id=tenant_pair.org_a_id,
            )
        )
    finally:
        db.close()
    assert result["matched_label"] == tenant_pair.label_a


@pytest.mark.skipif(not E2E_DB_URL, reason="E2E_DATABASE_URL não definido")
def test_exact_match_nao_alcanca_vertente_de_outra_org(tenant_pair, monkeypatch):
    seen = []
    _stub_llm(monkeypatch, seen)
    db = _fresh_db()
    try:
        result = asyncio.run(
            route_scoring_template(
                db,
                target_service=tenant_pair.label_a,
                explicit_template_id=None,
                organization_id=tenant_pair.org_b_id,
            )
        )
    finally:
        db.close()
    assert result["matched_label"] != tenant_pair.label_a
    if result.get("template"):
        assert result["template"].get("service_label") != tenant_pair.label_a
    for labels in seen:
        assert tenant_pair.label_a not in labels


@pytest.mark.skipif(not E2E_DB_URL, reason="E2E_DATABASE_URL não definido")
def test_fuzzy_match_nao_alcanca_vertente_de_outra_org(tenant_pair, monkeypatch):
    seen = []
    _stub_llm(monkeypatch, seen)
    db = _fresh_db()
    try:
        result = asyncio.run(
            route_scoring_template(
                db,
                target_service=f"prospecção {tenant_pair.label_a} empresas",
                explicit_template_id=None,
                organization_id=tenant_pair.org_b_id,
            )
        )
    finally:
        db.close()
    assert result["matched_label"] != tenant_pair.label_a
    for labels in seen:
        assert tenant_pair.label_a not in labels


@pytest.mark.skipif(not E2E_DB_URL, reason="E2E_DATABASE_URL não definido")
def test_id_explicito_estrangeiro_falha_fechado(tenant_pair, monkeypatch):
    """Uso direto por ID de outra org nunca entrega o template."""
    seen = []
    _stub_llm(monkeypatch, seen)
    db = _fresh_db()
    try:
        result = asyncio.run(
            route_scoring_template(
                db,
                target_service="qualquer serviço",
                explicit_template_id=tenant_pair.template_a_id,
                organization_id=tenant_pair.org_b_id,
            )
        )
    finally:
        db.close()
    assert result["matched_label"] != tenant_pair.label_a
    if result.get("template"):
        assert result["template"].get("service_label") != tenant_pair.label_a


@pytest.mark.skipif(not E2E_DB_URL, reason="E2E_DATABASE_URL não definido")
def test_api_get_direto_por_id_estrangeiro_retorna_404(tenant_pair):
    from fastapi import HTTPException

    from src.routes.scoring_templates import get_scoring_template

    db = _fresh_db()
    try:
        org_b = SimpleNamespace(id=tenant_pair.org_b_id)
        with pytest.raises(HTTPException) as exc:
            get_scoring_template(
                tenant_pair.template_a_id,
                db=db,
                _user=SimpleNamespace(id="u"),
                org=org_b,
            )
    finally:
        db.close()
    assert exc.value.status_code == 404


@pytest.mark.skipif(not E2E_DB_URL, reason="E2E_DATABASE_URL não definido")
def test_api_list_nao_expõe_vertente_de_outra_org(tenant_pair):
    from src.routes.scoring_templates import list_scoring_templates

    db = _fresh_db()
    try:
        org_b = SimpleNamespace(id=tenant_pair.org_b_id)
        payload = list_scoring_templates(
            scope="all",
            include_inactive=False,
            search=None,
            db=db,
            _user=SimpleNamespace(id="u"),
            org=org_b,
        )
    finally:
        db.close()
    labels = [t["service_label"] for t in payload["templates"]]
    assert tenant_pair.label_a not in labels


@pytest.mark.skipif(not E2E_DB_URL, reason="E2E_DATABASE_URL não definido")
def test_api_duplicar_fonte_estrangeira_retorna_404(tenant_pair):
    from fastapi import HTTPException

    from src.db.models import OrganizationRole
    from src.routes.scoring_templates import (
        CreateScoringTemplateRequest,
        create_scoring_template,
    )

    db = _fresh_db()
    try:
        org_b = SimpleNamespace(id=tenant_pair.org_b_id)
        body = CreateScoringTemplateRequest(
            service_label=_unique_label("Cópia B"),
            source_template_id=tenant_pair.template_a_id,
        )
        with pytest.raises(HTTPException) as exc:
            create_scoring_template(
                body,
                db=db,
                _user=SimpleNamespace(id="u"),
                org=org_b,
                member=SimpleNamespace(role=OrganizationRole.OWNER),
            )
    finally:
        db.close()
    assert exc.value.status_code == 404


@pytest.mark.skipif(not E2E_DB_URL, reason="E2E_DATABASE_URL não definido")
def test_api_patch_mesmo_nome_de_outra_org_nao_bloqueia(tenant_pair):
    """409 por nome só vale no escopo visível; nome privado de A não trava B."""
    from database.models import CampaignScoringTemplate
    from src.db.models import OrganizationRole
    from src.routes.scoring_templates import (
        PatchScoringTemplateRequest,
        patch_scoring_template,
    )

    db = _fresh_db()
    tmpl_b_id = None
    try:
        tmpl_b = CampaignScoringTemplate(
            service_label=_unique_label("Vertente B"),
            positive_signals=[],
            negative_signals=[],
            context_signals=[],
            is_active=True,
            organization_id=tenant_pair.org_b_id,
        )
        db.add(tmpl_b)
        db.flush()
        tmpl_b_id = tmpl_b.id
        db.commit()

        org_b = SimpleNamespace(id=tenant_pair.org_b_id)
        out = patch_scoring_template(
            str(tmpl_b_id),
            PatchScoringTemplateRequest(service_label=tenant_pair.label_a),
            db=db,
            _user=SimpleNamespace(id="u"),
            org=org_b,
            member=SimpleNamespace(role=OrganizationRole.OWNER),
        )
        assert out["service_label"] == tenant_pair.label_a
    finally:
        try:
            if tmpl_b_id is not None:
                db.query(CampaignScoringTemplate).filter(
                    CampaignScoringTemplate.id == tmpl_b_id
                ).delete(synchronize_session=False)
                db.commit()
        finally:
            db.close()
