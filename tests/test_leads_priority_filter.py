"""Filtro priority=HOT/WARM/COLD na listagem (preset "Quentes" real)."""
from types import SimpleNamespace

from src.routes import leads as leads_routes


class _FakeQuery:
    def __init__(self):
        self.filters = []
        self.order = None
        self._offset = 0
        self._limit = 0

    def filter(self, *a, **k):
        self.filters.append((a, k))
        return self

    def count(self):
        return 0

    def order_by(self, *a, **k):
        self.order = a
        return self

    def options(self, *a, **k):
        return self

    def offset(self, n):
        self._offset = n
        return self

    def limit(self, n):
        self._limit = n
        return self

    def all(self):
        return []


class _FakeDB:
    def __init__(self):
        self.queries = []

    def query(self, *a, **k):
        q = _FakeQuery()
        self.queries.append(q)
        return q


def _member():
    return SimpleNamespace(id="u1", user_id="u1")


def _org():
    return SimpleNamespace(id="org1")


def test_list_leads_aceita_priority_hot(monkeypatch):
    monkeypatch.setattr(leads_routes, "consultant_lead_scope", lambda m, q: q)
    monkeypatch.setattr(leads_routes, "_lead_summary", lambda lead: {})
    db = _FakeDB()
    result = leads_routes.list_leads(
        status=None, campaign_id=None, search=None, min_score=None,
        assigned=None, consultant_id=None, next_action_before=None,
        priority="HOT", limit=50, offset=0, db=db,
        _user=SimpleNamespace(id="u1"), _org=_org(), member=_member(),
    )
    assert result == {"total": 0, "leads": []}
    assert len(db.queries[0].filters) == 2  # org + priority


def test_list_leads_rejeita_priority_invalida(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(leads_routes, "consultant_lead_scope", lambda m, q: q)
    db = _FakeDB()
    try:
        leads_routes.list_leads(
            status=None, campaign_id=None, search=None, min_score=None,
            assigned=None, consultant_id=None, next_action_before=None,
            priority="QUENTE", limit=50, offset=0, db=db,
            _user=SimpleNamespace(id="u1"), _org=_org(), member=_member(),
        )
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("priority inválida deve ser rejeitada com 400")
