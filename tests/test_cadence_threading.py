"""Testes do threading completo dos follow-ups (roadmap-vendas 4.4).

Cobrem a lógica da montagem da cadeia `References` em `_thread_headers`
com um `db` fake (sem banco): as etapas anteriores devem acumular todos os
Message-IDs em ordem cronológica e `In-Reply-To` deve apontar para o último.
"""
from src.db.models import FollowUpStep
from src.services.cadence_service import _thread_headers


class _FakeQuery:
    """Cadeia `.filter().order_by().all()` que devolve os message-ids dados."""

    def __init__(self, ids):
        self._ids = ids

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def all(self):
        return [(mid,) for mid in self._ids]


class _FakeDb:
    """`db.query(col)` ignora a coluna e devolve a cadeia fake."""

    def __init__(self, ids):
        self._q = _FakeQuery(ids)

    def query(self, *_a):
        return self._q


def test_abertura_nao_tem_precedente():
    db = _FakeDb([])
    assert _thread_headers(db, "lead-1", FollowUpStep.OPENING) == (None, None)


def test_followup1_referencia_apenas_abertura():
    # FOLLOWUP_1 considera só etapas anteriores a ele (OPENING) → só a abertura.
    in_reply, refs = _thread_headers(_FakeDb(["<opening@m>"]), "lead-1", FollowUpStep.FOLLOWUP_1)
    assert in_reply == "<opening@m>"
    assert refs == ["<opening@m>"]


def test_followup2_acumula_cadeia_em_ordem():
    db = _FakeDb(["<opening@m>", "<fu1@m>"])
    in_reply, refs = _thread_headers(db, "lead-1", FollowUpStep.FOLLOWUP_2)
    assert in_reply == "<fu1@m>"
    assert refs == ["<opening@m>", "<fu1@m>"]


def test_closing_acumula_toda_a_cadeia():
    db = _FakeDb(["<opening@m>", "<fu1@m>", "<fu2@m>"])
    in_reply, refs = _thread_headers(db, "lead-1", FollowUpStep.CLOSING)
    assert in_reply == "<fu2@m>"
    assert refs == ["<opening@m>", "<fu1@m>", "<fu2@m>"]


def test_sem_etapas_anteriores_retorna_none():
    db = _FakeDb([])
    assert _thread_headers(db, "lead-1", FollowUpStep.FOLLOWUP_2) == (None, None)


def test_sem_lead_id_retorna_none():
    assert _thread_headers(_FakeDb(["<opening@m>"]), None, FollowUpStep.FOLLOWUP_1) == (None, None)