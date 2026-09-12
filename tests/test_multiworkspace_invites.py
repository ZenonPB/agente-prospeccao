"""Contrato de convites no modelo multi-workspace.

Um usuário pode continuar membro da organização A e aceitar um convite para B.
O aceite não deve procurar "qualquer membership" do usuário: a duplicidade é
sempre avaliada no par (organization_id, user_id).
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

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


def test_usuario_pode_aceitar_segundo_workspace_sem_perder_o_primeiro():
    user_id = uuid.uuid4()
    org_alpha = uuid.uuid4()
    org_pessoal = uuid.uuid4()
    token = "invite-token-multiworkspace"

    user = SimpleNamespace(id=user_id, email="zenon@example.com")
    membership_alpha = OrganizationMember(
        organization_id=org_alpha,
        user_id=user_id,
        role=OrganizationRole.MEMBER,
        sales_role=SalesRole.CONSULTOR,
    )
    invite_pessoal = Invite(
        id=uuid.uuid4(),
        organization_id=org_pessoal,
        email=user.email,
        token=token,
        role=OrganizationRole.OWNER,
        sales_role=SalesRole.MANAGER,
        invited_by_id=uuid.uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db = _Session(invite_pessoal, [membership_alpha])

    membership_pessoal = accept_invite(db, token, user)

    assert membership_pessoal.organization_id == org_pessoal
    assert membership_pessoal.user_id == user_id
    assert membership_pessoal.role == OrganizationRole.OWNER
    assert membership_pessoal.sales_role == SalesRole.MANAGER
    assert membership_alpha in db.memberships
    assert membership_pessoal in db.memberships
    assert invite_pessoal.accepted_at is not None
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
    invite = Invite(
        id=uuid.uuid4(),
        organization_id=org_id,
        email=user.email,
        token=token,
        role=OrganizationRole.MEMBER,
        sales_role=SalesRole.CONSULTOR,
        invited_by_id=uuid.uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db = _Session(invite, [existing])

    out = accept_invite(db, token, user)

    assert out is existing
    assert [m for m in db.memberships if m.organization_id == org_id] == [existing]
    assert not db.added
    assert invite.accepted_at is not None
