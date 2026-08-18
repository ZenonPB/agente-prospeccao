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

    def query(self, *_a):
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