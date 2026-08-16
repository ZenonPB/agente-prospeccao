"""Testes do registro de resposta inbound com variante (`_record_response_message`).

Cobre:
- derivar a variante da última `Message` enviada do lead;
- não criar `Message` quando não há envio anterior;
- não duplicar em re-chamada do webhook (última `Message` já é resposta).
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from src.services.inbound_email_service import _record_response_message


class _FakeBuilder:
    def __init__(self, results=None):
        self._results = [results] if results is not None else []

    def filter(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def first(self):
        return self._results.pop(0) if self._results else None


class _FakeDb:
    def __init__(self, last_sent=None):
        self._last_sent = last_sent
        self.added = []

    def query(self, *_a, **_k):
        return _FakeBuilder(self._last_sent)

    def add(self, obj):
        self.added.append(obj)


def _mk_last(variant, is_response=True, token="tok-1"):
    return SimpleNamespace(
        tracking_token=token, variant=variant, is_response=is_response,
        responded_at=None,
    )


def _lead(lead_id="l1"):
    return SimpleNamespace(id=lead_id)


def test_variante_da_ultima_mensagem_enviada():
    now = datetime.now(timezone.utc)
    db = _FakeDb(last_sent=_mk_last(variant="A", is_response=False))
    _record_response_message(db, _lead(), "resposta do lead", now)
    assert len(db.added) == 1
    resp = db.added[0]
    assert resp.is_response is True
    assert resp.variant == "A"
    assert resp.tracking_token == "tok-1"
    assert resp.sent_at == now
    assert resp.responded_at == now


def test_sem_envio_anterior_nao_cria_mensagem():
    now = datetime.now(timezone.utc)
    db = _FakeDb(last_sent=None)
    _record_response_message(db, _lead(), "resposta", now)
    assert db.added == []


def test_rechamada_webhook_nao_duplica():
    now = datetime.now(timezone.utc)
    last = _mk_last(variant="B")
    db = _FakeDb(last_sent=last)
    _record_response_message(db, _lead(), "segunda chamada", now)
    assert db.added == []
    assert last.responded_at == now