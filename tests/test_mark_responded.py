"""Registrar resposta manual: RESPONDIDO + cadência pausada + trilha."""
from types import SimpleNamespace

import pytest

from src.routes import leads as leads_routes


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDB:
    def __init__(self, lead, followups):
        self._lead = lead
        self._followups = followups
        self.added = []
        self.commits = 0

    def query(self, model):
        from src.db.models import Lead
        if model is Lead:
            return _FakeQuery([self._lead])
        return _FakeQuery(self._followups)

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1


def _lead():
    return SimpleNamespace(
        id="lead-1", organization_id="org1", status="CONTATADO",
        assigned_to_id="u1", last_contacted_at=None,
    )


def test_registrar_resposta_marca_respondido_e_pausa_cadencia(monkeypatch):
    from src.db.models import LeadStatus, FollowUpStatus

    monkeypatch.setattr(leads_routes, "_can_access_lead", lambda m, l: True)
    monkeypatch.setattr(leads_routes, "log_activity", lambda *a, **k: None)
    pending = SimpleNamespace(status="PENDING")
    db = _FakeDB(_lead(), [pending])

    result = leads_routes.mark_lead_responded(
        lead_id="lead-1",
        db=db,
        user=SimpleNamespace(id="u1"),
        _org=SimpleNamespace(id="org1"),
        member=SimpleNamespace(id="m1", user_id="u1"),
    )

    assert result["status"] == "RESPONDIDO"
    assert result["cancelled"] == 1
    assert pending.status == FollowUpStatus.CANCELLED
    assert db.commits == 1


def test_registrar_resposta_nao_regride_reuniao(monkeypatch):
    from src.db.models import LeadStatus

    monkeypatch.setattr(leads_routes, "_can_access_lead", lambda m, l: True)
    monkeypatch.setattr(leads_routes, "log_activity", lambda *a, **k: None)
    lead = _lead()
    lead.status = LeadStatus.REUNIAO_MARCADA
    db = _FakeDB(lead, [])

    leads_routes.mark_lead_responded(
        lead_id="lead-1",
        db=db,
        user=SimpleNamespace(id="u1"),
        _org=SimpleNamespace(id="org1"),
        member=SimpleNamespace(id="m1", user_id="u1"),
    )
    assert lead.status == LeadStatus.REUNIAO_MARCADA


def test_registrar_resposta_lead_inexistente_da_404(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(leads_routes, "_can_access_lead", lambda m, l: True)
    db = _FakeDB(None, [])
    with pytest.raises(HTTPException) as exc:
        leads_routes.mark_lead_responded(
            lead_id="nope", db=db,
            user=SimpleNamespace(id="u1"),
            _org=SimpleNamespace(id="org1"),
            member=SimpleNamespace(id="m1", user_id="u1"),
        )
    assert exc.value.status_code == 404
