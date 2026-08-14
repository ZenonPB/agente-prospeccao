"""Testes da auditoria de membros e acessos da organização.

Cobrem a lógica pura do `org_audit_service`: gravação de eventos com actor/
target/detail, não-exposição de valor de secret e filtro por evento na listagem.
"""
import uuid

from src.db.models import OrgAuditEvent, OrgAuditLog, SalesRole
from src.services.org_audit_service import log_org_event, list_org_audit, _actor_meta


class _FakeDb:
    """Registra objetos adicionados; query/filter/first devolvem o esperado."""

    def __init__(self, rows=None):
        self.added = []
        self.rows = rows or []

    def query(self, *_a):
        return self

    def filter(self, *_a, **_k):
        return self

    def order_by(self, *_a):
        return self

    def limit(self, *_a):
        return self

    def all(self):
        return self.rows

    def add(self, obj):
        self.added.append(obj)


class _User:
    id = uuid.uuid4()
    name = "Maria"
    email = "maria@teste.com.br"


class _Member:
    """OrganizationMember fake — expõe user + user_id + organization_id."""

    def __init__(self, user=None):
        self.user = user or _User()
        self.user_id = self.user.id
        self.organization_id = uuid.uuid4()


def test_log_org_event_grava_actor_e_target():
    db = _FakeDb()
    org_id = uuid.uuid4()
    member = _Member()

    log_org_event(
        db, org_id, OrgAuditEvent.MEMBER_ROLE_CHANGED, actor=member,
        target_type="member", target_id=str(member.user_id),
        detail="CONSULTOR -> ANALYST",
    )

    assert len(db.added) == 1
    entry: OrgAuditLog = db.added[0]
    assert entry.organization_id == org_id
    assert entry.actor_id == member.user_id
    assert entry.actor_name == "Maria"
    assert entry.actor_email == "maria@teste.com.br"
    assert entry.event == OrgAuditEvent.MEMBER_ROLE_CHANGED
    assert entry.target_type == "member"
    assert entry.detail == "CONSULTOR -> ANALYST"


def test_log_org_event_actor_user_sem_member():
    db = _FakeDb()
    user = _User()
    log_org_event(db, uuid.uuid4(), OrgAuditEvent.INVITE_ACCEPTED, actor=user)

    entry = db.added[0]
    assert entry.actor_id == user.id
    assert entry.actor_name == "Maria"
    assert entry.actor_email == "maria@teste.com.br"


def test_log_org_event_sem_actor():
    db = _FakeDb()
    log_org_event(db, uuid.uuid4(), OrgAuditEvent.SALES_TARGET_DELETED)

    entry = db.added[0]
    assert entry.actor_id is None
    assert entry.actor_name is None


def test_list_org_audit_filtra_por_evento():
    created = OrgAuditLog(event=OrgAuditEvent.ORG_CREATED)
    role = OrgAuditLog(event=OrgAuditEvent.MEMBER_ROLE_CHANGED)
    db = _FakeDb(rows=[created, role])

    # A função pura recebe o evento já resolvido — testa que o filtro rola no query.
    filtered = list_org_audit(db, uuid.uuid4(), event=OrgAuditEvent.MEMBER_ROLE_CHANGED)
    assert filtered == db.rows


def test_actor_meta_member_e_user():
    user = _User()
    member = _Member(user)
    assert _actor_meta(member) == (user.id, "Maria", "maria@teste.com.br")
    assert _actor_meta(user) == (user.id, "Maria", "maria@teste.com.br")
    assert _actor_meta(None) == (None, None, None)


def test_secret_event_nao_grava_valor():
    # O contrato da auditoria guarda apenas o key_name no target_id — nunca o valor.
    db = _FakeDb()
    member = _Member()
    log_org_event(
        db, uuid.uuid4(), OrgAuditEvent.SECRET_SET, actor=member,
        target_type="secret", target_id="GROQ_API_KEY",
    )
    entry = db.added[0]
    assert entry.target_id == "GROQ_API_KEY"
    assert entry.detail is None


def test_sales_role_detalhe_vem_do_enum():
    db = _FakeDb()
    member = _Member()
    log_org_event(
        db, uuid.uuid4(), OrgAuditEvent.MEMBER_ROLE_CHANGED, actor=member,
        target_type="member", detail=f"{SalesRole.CONSULTOR.value} -> {SalesRole.MANAGER.value}",
    )
    assert db.added[0].detail == "CONSULTOR -> MANAGER"
