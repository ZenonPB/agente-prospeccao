"""Idempotência de conversão: 1 venda = 1 registro (sem duplicar no BI)."""
from types import SimpleNamespace

from src.routes.leads import find_duplicate_conversion


class _FakeQuery:
    def __init__(self, row):
        self._row = row

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def first(self):
        return self._row


class _FakeDB:
    def __init__(self, row=None):
        self._row = row

    def query(self, *a, **k):
        return _FakeQuery(self._row)


def test_segunda_conversao_igual_eh_duplicata():
    db = _FakeDB(row=SimpleNamespace(id="conv-1", offer_key="trophies"))
    dup = find_duplicate_conversion(
        db, lead_id="lead-1", offer_key="trophies", lead_opportunity_id=None,
    )
    assert dup is not None


def test_conversao_de_oferta_diferente_nao_eh_duplicata():
    db = _FakeDB(row=None)
    dup = find_duplicate_conversion(
        db, lead_id="lead-1", offer_key="trophies", lead_opportunity_id=None,
    )
    assert dup is None
