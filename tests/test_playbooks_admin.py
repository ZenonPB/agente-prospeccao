"""Regressão dos playbooks: owner/admin editavam/removiam apenas por string
(`actor.role in ("OWNER", "ADMIN")` nunca era True — o valor do enum é
minúsculo). Agora a comparação é por enum."""
import uuid
from types import SimpleNamespace

from src.db.models import OrganizationRole
from src.routes.playbooks import UpdatePlaybookRequest, update_playbook


class _FakePb:
    id = None
    organization_id = "org-1"
    author_id = "user-outro"  # outro autor — só admin/owner poderia editar
    author = None
    vertical = None
    subject = "Assunto antigo"
    body = "Corpo"
    tags = []
    created_at = None
    updated_at = None


class _FakeQuery:
    def filter(self, *_a, **_k):
        return self

    def first(self):
        return _FakePb()


class _FakeDb:
    def __init__(self):
        self.commits = 0
        self.refreshed = 0

    def query(self, *_a):
        return _FakeQuery()

    def commit(self):
        self.commits += 1

    def refresh(self, _obj):
        self.refreshed += 1


def _call(role):
    from fastapi import HTTPException

    db = _FakeDb()
    org = SimpleNamespace(id="org-1")
    actor = SimpleNamespace(role=role)
    user = SimpleNamespace(id="user-ator")
    body = UpdatePlaybookRequest(subject="Assunto novo")
    try:
        out = update_playbook(str(uuid.uuid4()), body, db, user, org, actor)
    except HTTPException as exc:
        return {"error": exc.status_code}
    return {"out": out, "commits": db.commits}


def test_owner_pode_editar_playbook_de_outro_autor():
    result = _call(OrganizationRole.OWNER)
    assert "error" not in result
    assert result["commits"] == 1
    assert result["out"]["subject"] == "Assunto novo"


def test_admin_pode_editar_playbook_de_outro_autor():
    result = _call(OrganizationRole.ADMIN)
    assert "error" not in result
    assert result["out"]["subject"] == "Assunto novo"


def test_membro_sem_ser_autor_recebe_403():
    result = _call(OrganizationRole.MEMBER)
    assert result.get("error") == 403