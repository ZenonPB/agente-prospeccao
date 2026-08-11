"""Testes do módulo de SLA / leads parados (roadmap-vendas 4.10)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.db.models import LeadStatus, Message, Organization, OrganizationRole
from src.services.sla_service import _days_since, _alert, compute_sla_alerts


def test_days_since_zero():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    anchor = datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc)
    assert _days_since(anchor, now) == 0


def test_days_since_naive_anchor():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    anchor = datetime(2026, 8, 5, 12, 0)  # sem tzinfo
    assert _days_since(anchor, now) == 5


def test_alert_structure():
    class FakeLead:
        id = "abc"
        company_name = "Empresa Teste"
        city = "Araraquara"
        state = "SP"
        status = type("S", (), {"value": "QUALIFICADO"})()
        qualification_score = 75
        assigned_to = None
        last_contacted_at = None
        next_action_at = None

    alert = _alert(
        FakeLead(), "QUALIFICADO_NO_CONTACT",
        "Apto sem contato há 6 dia(s)", 6,
    )
    assert alert["alert_type"] == "QUALIFICADO_NO_CONTACT"
    assert alert["company_name"] == "Empresa Teste"
    assert alert["days_since"] == 6
    assert alert["status"] == "QUALIFICADO"
    assert alert["last_contacted_at"] is None


# ---------------------------------------------------------------------------
# compute_sla_alerts — as 3 regras com um `db` fake (sem banco)
# ---------------------------------------------------------------------------

def _mk_lead(lead_id, status, days_ago, **kwargs):
    """Lead fake com âncoras relativas a `now` (dias para trás)."""
    now = datetime.now(timezone.utc)
    base = {
        "id": lead_id,
        "company_name": f"Empresa {lead_id}",
        "city": "Araraquara",
        "state": "SP",
        "status": status,
        "qualification_score": 75,
        "assigned_to": None,
        "last_contacted_at": None,
        "next_action_at": None,
        "created_at": now - timedelta(days=days_ago),
        "updated_at": now - timedelta(days=days_ago),
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


class _FakeOrg:
    sla_qualified_no_contact_days = 5
    sla_responded_no_next_action_days = 2
    sla_opened_no_response_days = 2


class _FakeSubquery:
    """Subquery fake: os filtros não são avaliados, só `.c` precisa existir."""

    c = SimpleNamespace(
        lead_id="lead_id",
        last_opened=datetime(2000, 1, 1, tzinfo=timezone.utc),
    )


class _FakeBuilder:
    """Cadeia `.filter().join().limit().all()` que devolve resultados enfileirados.

    Cada elemento de `results` é uma lista devolvida por um `.all()` (ou o
    objeto devolvido por `.first()`/`.subquery()`), na ordem das consultas.
    """

    def __init__(self, results):
        self._results = list(results)

    def filter(self, *_a, **_k):
        return self

    def join(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def group_by(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def first(self):
        return self._results.pop(0) if self._results else None

    def subquery(self):
        return _FakeSubquery()

    def all(self):
        return self._results.pop(0) if self._results else []


class _FakeDb:
    """`db.query(col)` roteia por entidade: Organization/Message/Lead."""

    def __init__(self, org, q_rows, r_rows, o_rows):
        self._org = org
        self._q = _FakeBuilder([q_rows, r_rows, o_rows])

    def query(self, *cols):
        if any(c is Organization for c in cols):
            return _FakeBuilder([self._org])
        if any(c is Message for c in cols):
            return _FakeBuilder([])
        return self._q


class _FullAccessMember:
    role = OrganizationRole.OWNER
    sales_role = None
    user_id = "u1"


def _alerts_for(q_rows, r_rows, o_rows):
    return compute_sla_alerts(
        _FakeDb(_FakeOrg(), q_rows, r_rows, o_rows),
        org_id="org-1",
        member=_FullAccessMember(),
        limit=50,
    )


def test_regra_qualificado_sem_contato():
    lead = _mk_lead("l1", LeadStatus.QUALIFICADO, days_ago=7)
    alerts = _alerts_for([lead], [], [])
    assert len(alerts) == 1
    a = alerts[0]
    assert a["id"] == "l1"
    assert a["alert_type"] == "QUALIFICADO_NO_CONTACT"
    assert a["status"] == "QUALIFICADO"
    assert a["days_since"] == 7
    assert a["qualification_score"] == 75


def test_regra_respondido_sem_proximo_passo():
    lead = _mk_lead("l2", LeadStatus.RESPONDIDO, days_ago=3)
    alerts = _alerts_for([], [lead], [])
    assert len(alerts) == 1
    assert alerts[0]["alert_type"] == "RESPONDIDO_NO_NEXT_ACTION"
    assert alerts[0]["id"] == "l2"


def test_regra_abriu_sem_responder():
    lead = _mk_lead("l3", LeadStatus.CONTATADO, days_ago=6)
    last_opened = datetime.now(timezone.utc) - timedelta(days=6)
    alerts = _alerts_for([], [], [(lead, last_opened)])
    assert len(alerts) == 1
    a = alerts[0]
    assert a["alert_type"] == "OPENED_NO_RESPONSE"
    assert a["days_since"] == 6
    assert a["opened_at"] is not None


def test_ordena_por_criticidade():
    q = _mk_lead("q1", LeadStatus.QUALIFICADO, days_ago=9)
    r = _mk_lead("r1", LeadStatus.RESPONDIDO, days_ago=3)
    opened = datetime.now(timezone.utc) - timedelta(days=5)
    o = _mk_lead("o1", LeadStatus.CONTATADO, days_ago=5)
    alerts = _alerts_for([q], [r], [(o, opened)])
    assert [a["id"] for a in alerts] == ["q1", "o1", "r1"]
    assert alerts[0]["days_since"] >= alerts[1]["days_since"] >= alerts[2]["days_since"]


def test_sem_alertas_retorna_lista_vazia():
    assert _alerts_for([], [], []) == []