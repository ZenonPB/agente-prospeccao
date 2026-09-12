from __future__ import annotations

import uuid
from types import SimpleNamespace

from sqlalchemy_memory import ConsultaMemoria

from src.db.models import Invite, OrganizationRole, SalesRole
from src.services.invite_service import create_invite, get_invite_by_token, hash_invite_token


class _Session:
    def __init__(self, invites=None):
        self.invites = list(invites or [])

    def query(self, model, *_args):
        if model is Invite:
            return ConsultaMemoria("invites", [{"invites": item} for item in self.invites])
        raise AssertionError(f"query inesperada: {model}")

    def add(self, row):
        if isinstance(row, Invite):
            self.invites.append(row)

    def flush(self):
        return None


def test_novo_convite_persiste_apenas_hash_do_token():
    db = _Session()
    invite = create_invite(
        db,
        organization_id=uuid.uuid4(),
        email="Pessoa@Example.com",
        invited_by_id=uuid.uuid4(),
        role=OrganizationRole.MEMBER,
        sales_role=SalesRole.CONSULTOR,
    )

    raw_token = invite._raw_token
    assert raw_token
    assert invite.token != raw_token
    assert invite.token == hash_invite_token(raw_token)
    assert invite.email == "pessoa@example.com"
    assert get_invite_by_token(db, raw_token) is invite


def test_lookup_migra_token_legado_sem_quebrar_link_existente():
    raw_token = "legacy-invite-token-123456789"
    legacy = SimpleNamespace(token=raw_token)
    db = _Session([legacy])

    resolved = get_invite_by_token(db, raw_token)

    assert resolved is legacy
    assert legacy.token == hash_invite_token(raw_token)
    assert raw_token not in legacy.token
