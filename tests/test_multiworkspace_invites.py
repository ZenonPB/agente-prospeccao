"""Contrato de convites no modelo multi-workspace.

Um usuário pode continuar membro da organização A e aceitar um convite para B.
O aceite não deve procurar "qualquer membership" do usuário: a duplicidade é
sempre avaliada no par (organization_id, user_id). Ownership é separado desse
fluxo e só pode mudar por transferência explícita.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException

from sqlalchemy_memory import ConsultaMemoria

from src.db.models import Invite, OrganizationMember, OrganizationRole, SalesRole
from src.services.invite_service import accept_invite


class _Session:
    def __init__(self, invite, memberships):
        self.invite = invite
        self.memberships = list(memberships)
        self.added = []
        self.commits = 0

    def query(self, model, *_args):
        if model is Invite:
            return ConsultaMemoria(
                "invites",
                [{"invites": self.invite}],
            )
        if model is OrganizationMember:
            rows = [
                {"organization_members": membership}
                for membership in self.memberships
            ]
            return ConsultaMemoria("organization_members", rows)
        raise AssertionError(f"query inesperada: {model}")

    def add(self, row):
        self.added.append(row)
        if isinstance(row, OrganizationMember):
            self.memberships.append(row)

    def commit(self):
        self.commits += 1

    def refresh(self, _row):
        return None


def _invite(*, org_id, email, token, role=OrganizationRole.MEMBER, sales_role=SalesRole.CONSULTOR):
    return Invite(
        id=uuid.uuid4(),
        organization_id=org_id,
        email=email,
        token=token,
        role=role,
        sales_role=sales_role,
        invited_by_id=uuid.uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )


def test_usuario_pode_aceitar_segundo_workspace_sem_perder_o_primeiro():
    user_id = uuid.uuid4()
    org_alpha = uuid.uuid4()
    org_secundaria = uuid.uuid4()
    token = "invite-token-multiworkspace"

    user = SimpleNamespace(id=user_id, email="zenon@example.com")
    membership_alpha = OrganizationMember(
        organization_id=org_alpha,
        user_id=user_id,
        role=OrganizationRole.MEMBER,
        sales_role=SalesRole.CONSULTOR,
    )
    invite_secundaria = _invite(
        org_id=org_secundaria,
        email=user.email,
        token=token,
        role=OrganizationRole.ADMIN,
        sales_role=SalesRole.MANAGER,
    )
    db = _Session(invite_secundaria, [membership_alpha])

    membership_secundaria = accept_invite(db, token, user)

    assert membership_secundaria.organization_id == org_secundaria
    assert membership_secundaria.user_id == user_id
    assert membership_secundaria.role == OrganizationRole.ADMIN
    assert membership_secundaria.sales_role == SalesRole.MANAGER
    assert membership_alpha in db.memberships
    assert membership_secundaria in db.memberships
    assert invite_secundaria.accepted_at is not None
    assert db.commits >= 1


def test_aceite_reutiliza_membership_apenas_na_mesma_organizacao():
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    token = "invite-token-existing-membership"

    user = SimpleNamespace(id=user_id, email="membro@example.com")
    existing = OrganizationMember(
        organization_id=org_id,
        user_id=user_id,
        role=OrganizationRole.MEMBER,
        sales_role=SalesRole.CONSULTOR,
    )
    invite = _invite(org_id=org_id, email=user.email, token=token)
    db = _Session(invite, [existing])

    out = accept_invite(db, token, user)

    assert out is existing
    assert [m for m in db.memberships if m.organization_id == org_id] == [existing]
    assert not db.added
    assert invite.accepted_at is not None


def test_convite_owner_legado_nao_cria_segundo_proprietario():
    user = SimpleNamespace(id=uuid.uuid4(), email="novo-owner@example.com")
    invite = _invite(
        org_id=uuid.uuid4(),
        email=user.email,
        token="invite-token-owner-legado",
        role=OrganizationRole.OWNER,
        sales_role=SalesRole.MANAGER,
    )
    db = _Session(invite, [])

    with pytest.raises(HTTPException) as exc:
        accept_invite(db, invite.token, user)

    assert exc.value.status_code == 400
    assert "transfer" in str(exc.value.detail).lower()
    assert not db.added
    assert invite.accepted_at is None
