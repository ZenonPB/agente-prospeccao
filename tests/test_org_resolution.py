"""Resolução de org/membership por request (multi-org real).

O org switcher envia `X-Organization-Id`; o backend só resolve a org pedida
se o usuário for membro dela (senão 403). Sem header, cai na primeira
membership (comportamento legado de uma única org).
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.auth.dependencies import _resolve_request_membership


class _FakeQuery:
    def __init__(self, result):
        self.result = result

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self.result


class _FakeDb:
    def __init__(self, result):
        self.result = result
        self.query_count = 0

    def query(self, *_a):
        self.query_count += 1
        return _FakeQuery(self.result)


def _member(org_id, role):
    return SimpleNamespace(organization_id=org_id, role=role, user_id="user-1")


def _req(org_id=None):
    headers = {}
    if org_id:
        headers["X-Organization-Id"] = org_id
    return SimpleNamespace(headers=headers)


def test_sem_header_cai_na_primeira_membership():
    member = _member("org-1", "owner")
    out = _resolve_request_membership(_FakeDb(member), SimpleNamespace(id="u"), None)
    assert out is member


def test_header_resolve_membership_da_org_solicitada():
    member = _member("org-2", "manager")
    out = _resolve_request_membership(_FakeDb(member), SimpleNamespace(id="u"), _req("org-2"))
    assert out is member


def test_header_com_org_fora_das_memberships_levanta_403():
    with pytest.raises(HTTPException) as exc:
        _resolve_request_membership(_FakeDb(None), SimpleNamespace(id="u"), _req("org-99"))
    assert exc.value.status_code == 403


def test_orgs_me_serializa_membership_ja_resolvida_sem_escolher_primeira_org(monkeypatch):
    """`/orgs/me` não pode refazer lookup global e voltar ao primeiro workspace."""
    import src.routes.orgs as orgs_module

    organization = SimpleNamespace(
        id="org-2",
        name="Vendas Samuel e Zenon",
        slug="vendas-samuel-zenon",
        auto_send_email=False,
        daily_email_limit=40,
        send_window_start="09:00",
        send_window_end="17:00",
        email_from=None,
        sla_qualified_no_contact_days=5,
        sla_responded_no_next_action_days=2,
        sla_opened_no_response_days=2,
        qualification_threshold=60,
        webhook_url=None,
        scheduling_url=None,
    )
    member = SimpleNamespace(
        organization_id=organization.id,
        organization=organization,
        user_id="user-1",
        role=SimpleNamespace(name="OWNER"),
        sales_role=SimpleNamespace(value="MANAGER"),
    )
    db = _FakeDb(result=SimpleNamespace(organization_id="org-1"))
    monkeypatch.setattr(orgs_module, "sends_today", lambda *_a, **_k: (0, None))

    payload = orgs_module.get_my_org(db=db, member=member)

    assert payload["organization"]["id"] == "org-2"
    assert payload["organization"]["name"] == "Vendas Samuel e Zenon"
    assert payload["membership"]["role"] == "OWNER"
    # A membership já foi resolvida pela dependência tenant-aware. A rota não
    # pode escolher outra organização fazendo uma nova query por user_id.
    assert db.query_count == 0
