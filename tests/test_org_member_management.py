"""Testes de gestão de membros (roadmap-vendas 3.3.3).

Testa a desatribuição automática de leads quando um membro é removido ou sai
da organização, além das validações de ownership.
"""
import uuid
from src.db.models import (
    User,
    Organization,
    OrganizationMember,
    OrganizationRole,
    SalesRole,
    Lead,
    LeadActivityAction,
)
from src.services.org_service import unassign_user_leads_in_org


def test_unassign_user_leads_in_org():
    # Teste unitário da função unassign_user_leads_in_org (sem banco real mockado por objetos simples)
    class FakeQuery:
        def __init__(self, items):
            self.items = items

        def filter(self, *args):
            return self

        def all(self):
            return self.items

    class FakeLead:
        def __init__(self, lead_id, org_id, user_id):
            self.id = lead_id
            self.organization_id = org_id
            self.assigned_to_id = user_id
            self.assigned_at = "now"

    class FakeDB:
        def __init__(self, leads):
            self.leads = leads
            self.added = []

        def query(self, model):
            return FakeQuery(self.leads)

        def add(self, obj):
            self.added.append(obj)

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    actor_id = uuid.uuid4()

    lead1 = FakeLead(uuid.uuid4(), org_id, user_id)
    lead2 = FakeLead(uuid.uuid4(), org_id, user_id)
    db = FakeDB([lead1, lead2])

    count = unassign_user_leads_in_org(
        db,
        org_id=org_id,
        user_id=user_id,
        actor_user_id=actor_id,
        reason="Teste de remoção",
    )

    assert count == 2
    assert lead1.assigned_to_id is None
    assert lead1.assigned_at is None
    assert lead2.assigned_to_id is None
    assert len(db.added) == 2
    assert db.added[0].action == LeadActivityAction.UNASSIGNED
    assert db.added[0].detail == "Teste de remoção"
