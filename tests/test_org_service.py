"""Testes do onboarding multi-org (roadmap-vendas 3.3.1).

Cobrem a lógica pura de criação de organização: slugificação do nome e a
criação de org manual com o usuário como OWNER (sales_role MANAGER).
"""
from src.db.models import OrganizationRole, SalesRole
from src.services.org_service import slugify, create_organization


class _FakeDb:
    """db.query(...).filter(...).first() → None (slug livre); add/flush no-op."""

    def __init__(self):
        self.added = []

    def query(self, *_a):
        return self

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return None

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        return None


class _User:
    id = "user-1"


def test_slugify_simples():
    assert slugify("AlphaMec") == "alphamec"


def test_slugify_normaliza_acentos_e_separadores():
    assert slugify("AlphaMec & Cia Ltda") == "alphamec-cia-ltda"
    assert slugify("Consultoria  ").startswith("consultoria")


def test_slugify_vazio_fallback():
    assert slugify("   ") == "workspace"


def test_create_organization_dono_owner_e_manager():
    db = _FakeDb()
    org = create_organization(db, "AlphaMec", _User(), email_from="vendas@alphamec.com.br")

    assert org.name == "AlphaMec"
    assert org.slug == "alphamec"
    assert org.email_from == "vendas@alphamec.com.br"

    memberships = [m for m in db.added if hasattr(m, "role")]
    assert len(memberships) == 1
    assert memberships[0].organization_id == org.id
    assert memberships[0].user_id == "user-1"
    assert memberships[0].role == OrganizationRole.OWNER
    assert memberships[0].sales_role == SalesRole.MANAGER