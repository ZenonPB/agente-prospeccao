"""Regressão do auto-envio de cadência (bug: NameError no scheduler).

O `run_due` chamava `org_sends_today` (função inexistente) em vez de
`sends_today` — o scheduler capturava o erro por ciclo e o auto-envio
nunca acontecia, de forma silenciosa.
"""
from types import SimpleNamespace

from src.services.cadence_service import run_due


class _FakeQuery:
    def __init__(self, db):
        self.db = db

    def join(self, *_a, **_k):
        return self

    def filter(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def all(self):
        return self.db.due_rows

    def first(self):
        return self.db.org

    def scalar(self):
        # `sends_today` chama scalar() duas vezes (hoje e na hora).
        return self.db.scalar_queue.pop(0)


class _FakeDb:
    def __init__(self, due_rows, org, today=0, hour=0):
        self.due_rows = due_rows
        self.org = org
        self.scalar_queue = [today, hour]

    def query(self, *_a):
        return _FakeQuery(self)


def _org():
    return SimpleNamespace(
        daily_email_limit=40,
        send_window_start="09:00",
        send_window_end="17:00",
        auto_send_email=True,
    )


def _follow_up(org_id):
    return SimpleNamespace(
        lead=SimpleNamespace(organization_id=org_id),
        step=None,
        status=None,
        scheduled_at=None,
    )


def test_run_due_ne_vai_a_nameerror_com_conta_de_hoje():
    """Teto diário já atingido (40/40) → posterga sem NameError e sem enviar."""
    db = _FakeDb(
        due_rows=[_follow_up("org-1")],
        org=_org(),
        today=40,
        hour=0,
    )
    sent, deferred = run_due(db)
    assert sent == 0
    assert deferred == 1


def test_run_due_sem_follow_ups_retorna_zero():
    db = _FakeDb(due_rows=[], org=_org(), today=0, hour=0)
    sent, deferred = run_due(db)
    assert sent == 0
    assert deferred == 0