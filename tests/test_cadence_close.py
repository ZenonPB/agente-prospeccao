"""Testes do auto-PERDIDO no encerramento da cadência (business-rules — dia 14).

Cobertura unitária (sem banco): função pura `_grace_elapsed` e o fluxo de
`close_expired_cadences` com um `db` fake no padrão de `test_sla_service.py`.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.db.models import FollowUp, LeadActivityAction, LeadStatus, LostReason
from src.services.cadence_close_service import _grace_elapsed, close_expired_cadences

_NOW = datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)
_OLD = _NOW - timedelta(days=10)


# ---------------------------------------------------------------------------
# _grace_elapsed — função pura
# ---------------------------------------------------------------------------

def test_grace_nao_vencida():
    assert not _grace_elapsed(_NOW - timedelta(days=5), _NOW, 7)


def test_grace_no_limiar_exato():
    assert _grace_elapsed(_NOW - timedelta(days=7), _NOW, 7)


def test_grace_vencida():
    assert _grace_elapsed(_OLD, _NOW, 7)


def test_grace_naive_tratado_como_utc():
    naive_old = _OLD.replace(tzinfo=None)
    assert _grace_elapsed(naive_old, _NOW, 7)


def test_grace_sem_data():
    assert not _grace_elapsed(None, _NOW, 7)


# ---------------------------------------------------------------------------
# close_expired_cadences — fluxo com db fake
# ---------------------------------------------------------------------------

class _FakeBuilder:
    """Cadeia `.join().filter().all()` devolvendo resultados enfileirados."""

    def __init__(self, results):
        self._results = list(results)

    def filter(self, *_a, **_k):
        return self

    def join(self, *_a, **_k):
        return self

    def group_by(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def all(self):
        return self._results.pop(0) if self._results else []


class _FakeDb:
    """`db.query(col)` roteia por entidade: FollowUp (encerramentos enviados)."""

    def __init__(self, closing):
        self._closing = closing
        self.committed = 0
        self.added = []

    def query(self, *cols):
        # `db.query(FollowUp)` passa a classe — roteia por identidade.
        if any(c is FollowUp for c in cols):
            return _FakeBuilder([self._closing])
        return _FakeBuilder([])

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed += 1


def _mk_lead(lead_id, status=LeadStatus.CONTATADO, opt_out=False):
    return SimpleNamespace(id=lead_id, status=status, opt_out=opt_out)


def _mk_closing(lead, sent_at=_OLD):
    return SimpleNamespace(lead=lead, sent_at=sent_at)


def _run(closing, grace_days=7):
    db = _FakeDb(closing)
    n = close_expired_cadences(db, now=_NOW, grace_days=grace_days)
    return db, n


def test_encerramento_recente_nao_marca():
    lead = _mk_lead("l1")
    db, n = _run([_mk_closing(lead, sent_at=_NOW - timedelta(days=2))])
    assert n == 0
    assert lead.status == LeadStatus.CONTATADO
    assert db.committed == 0


def test_encerramento_vencido_marca_perdido():
    lead = _mk_lead("l2")
    db, n = _run([_mk_closing(lead)])
    assert n == 1
    assert lead.status == LeadStatus.PERDIDO
    assert lead.lost_reason == LostReason.NAO_RESPONDEU
    assert db.committed == 1
    # Trilha: STATUS_CHANGED (PERDIDO) + action LOST.
    assert len(db.added) == 2
    assert db.added[0].status_from == LeadStatus.CONTATADO
    assert db.added[0].status_to == LeadStatus.PERDIDO
    assert db.added[1].action == LeadActivityAction.LOST


def test_opt_out_nao_marca():
    lead = _mk_lead("l3", opt_out=True)
    db, n = _run([_mk_closing(lead)])
    assert n == 0
    assert lead.status == LeadStatus.CONTATADO


def test_status_avancado_nao_sobrescreve():
    # Lead respondeu depois do encerramento (status RESPONDIDO) → nunca PERDIDO.
    lead = _mk_lead("l4", status=LeadStatus.RESPONDIDO)
    db, n = _run([_mk_closing(lead)])
    assert n == 0
    assert lead.status == LeadStatus.RESPONDIDO


def test_sem_lead_nao_quebra():
    db, n = _run([_mk_closing(None)])
    assert n == 0
    assert db.committed == 0


def test_grace_days_zero_desativa():
    lead = _mk_lead("l5")
    db, n = _run([_mk_closing(lead)], grace_days=0)
    assert n == 0
    assert lead.status == LeadStatus.CONTATADO


def test_sem_encerramentos_nao_commita():
    db, n = _run([])
    assert n == 0
    assert db.committed == 0