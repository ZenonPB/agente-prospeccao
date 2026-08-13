"""Testes do re-enfileiramento de leads PERDIDO (business-rules — 90 dias).

Cobertura unitária (sem banco): função pura `_is_expired` e o fluxo de
`requeue_expired_lost` com um `db` fake no padrão de `test_sla_service.py`.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.db.models import LeadActivity, LeadStatus, LostReason
from src.services.requeue_service import (
    REQUEUE_LOST_REASONS,
    _is_expired,
    requeue_expired_lost,
)

_NOW = datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)
_OLD = _NOW - timedelta(days=91)


def test_requeue_lost_reasons_apenas_tempo():
    assert REQUEUE_LOST_REASONS == (LostReason.NAO_RESPONDEU,)


# ---------------------------------------------------------------------------
# _is_expired — função pura
# ---------------------------------------------------------------------------

def test_is_expired_abaixo_do_limiar():
    recent = _NOW - timedelta(days=30, minutes=1)
    assert not _is_expired(recent, _NOW, 90)


def test_is_expired_no_limiar_exato():
    assert _is_expired(_NOW - timedelta(days=90), _NOW, 90)


def test_is_expired_vencido():
    assert _is_expired(_OLD, _NOW, 90)


def test_is_expired_naive_tratado_como_utc():
    naive_old = _OLD.replace(tzinfo=None)
    assert _is_expired(naive_old, _NOW, 90)


def test_is_expired_sem_data():
    assert not _is_expired(None, _NOW, 90)


# ---------------------------------------------------------------------------
# requeue_expired_lost — fluxo com db fake
# ---------------------------------------------------------------------------

class _FakeBuilder:
    """Cadeia `.filter().group_by().all()` devolvendo resultados enfileirados."""

    def __init__(self, results):
        self._results = list(results)

    def filter(self, *_a, **_k):
        return self

    def group_by(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def all(self):
        return self._results.pop(0) if self._results else []


class _FakeDb:
    """`db.query(col)` roteia por entidade: LeadActivity (datas de perda) vs Lead."""

    def __init__(self, candidates, lost_rows=None):
        self._candidates = candidates
        self._lost_rows = lost_rows or []
        self.committed = 0
        self.added = []

    def query(self, *cols):
        classes = [getattr(c, "class_", None) for c in cols]
        if LeadActivity in classes:
            return _FakeBuilder([self._lost_rows])
        return _FakeBuilder([self._candidates])

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed += 1


def _mk_lost(lead_id, reason=None, opt_out=False, updated_at=_OLD, status=LeadStatus.PERDIDO):
    return SimpleNamespace(
        id=lead_id,
        status=status,
        opt_out=opt_out,
        lost_reason=reason,
        updated_at=updated_at,
    )


def _run(candidates, lost_rows=None, days=90):
    db = _FakeDb(candidates, lost_rows)
    n = requeue_expired_lost(db, now=_NOW, days=days)
    return db, n


def test_perda_deliberada_nao_volta():
    lead = _mk_lost("l1", reason=LostReason.PRECO)
    db, n = _run([lead])
    assert n == 0
    assert lead.status == LeadStatus.PERDIDO
    assert db.committed == 0


def test_opt_out_nao_volta():
    lead = _mk_lost("l2", opt_out=True)
    db, n = _run([lead])
    assert n == 0
    assert lead.status == LeadStatus.PERDIDO
    assert db.committed == 0


def test_menos_de_90_dias_nao_volta():
    lead = _mk_lost("l3", updated_at=_NOW - timedelta(days=10))
    db, n = _run([lead])
    assert n == 0
    assert lead.status == LeadStatus.PERDIDO


def test_sem_motivo_vencido_volta():
    lead = _mk_lost("l4", reason=None)
    db, n = _run([lead])
    assert n == 1
    assert lead.status == LeadStatus.NOVO
    assert lead.lost_reason is None
    assert db.committed == 1
    assert db.added and db.added[0].detail  # trilha registrada
    assert db.added[0].status_to == LeadStatus.NOVO
    assert db.added[0].status_from == LeadStatus.PERDIDO


def test_nao_respondeu_vencido_volta():
    lead = _mk_lost("l5", reason=LostReason.NAO_RESPONDEU)
    _, n = _run([lead])
    assert n == 1
    assert lead.status == LeadStatus.NOVO


def test_usa_trilha_quando_existe():
    # updated_at recente, mas a trilha registra perda antiga → volta (usa a trilha).
    lead = _mk_lost("l6", updated_at=_NOW - timedelta(days=1))
    db, n = _run([lead], lost_rows=[SimpleNamespace(lead_id=lead.id, lost_at=_OLD)])
    assert n == 1
    assert lead.status == LeadStatus.NOVO


def test_days_zero_desativa():
    lead = _mk_lost("l7", reason=None)
    db, n = _run([lead], days=0)
    assert n == 0
    assert lead.status == LeadStatus.PERDIDO
    assert db.committed == 0


def test_sem_candidatos_nao_commita():
    db, n = _run([])
    assert n == 0
    assert db.committed == 0