"""Templates globais (seeds, `organization_id IS NULL`) são read-only via PATCH:
edição por qualquer usuário afetaria o scoring de todas as orgs."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.routes.scoring_templates import (
    PatchScoringTemplateRequest,
    patch_scoring_template,
)


class _FakeQuery:
    def __init__(self, tmpl):
        self.tmpl = tmpl

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self.tmpl


class _FakeTmpl:
    id = "template-1"
    organization_id = None
    service_label = "Genérico"
    positive_signals = []
    negative_signals = []
    context_signals = []
    requires_technical_report = True
    requires_business_data = True
    extra_instructions = None
    playbook = {}
    is_generated = False
    is_active = True
    created_at = None
    updated_at = None


def _db_with(tmpl):
    return SimpleNamespace(
        query=lambda *_a: _FakeQuery(tmpl),
        commit=lambda: None,
        refresh=lambda _o: None,
    )


def test_patch_em_template_global_recebe_400():
    db = _db_with(_FakeTmpl())
    body = PatchScoringTemplateRequest(service_label="Renomeado")
    with pytest.raises(HTTPException) as exc:
        patch_scoring_template(
            "template-1", body, db,
            _user=SimpleNamespace(id="u"),
            org=SimpleNamespace(id="org-1"),
        )
    assert exc.value.status_code == 400


def test_patch_em_template_da_org_funciona():
    class TmplOrg(_FakeTmpl):
        organization_id = "org-1"

    db = _db_with(TmplOrg())
    body = PatchScoringTemplateRequest(is_active=False)
    out = patch_scoring_template(
        "template-1", body, db,
        _user=SimpleNamespace(id="u"),
        org=SimpleNamespace(id="org-1"),
    )
    assert out["is_active"] is False