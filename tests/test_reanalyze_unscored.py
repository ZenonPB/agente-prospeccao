"""Reanálise seletiva: `/campaigns/{id}/reanalyze?unscored_only=true`.

Verifica o enfileiramento do job com o filtro de "não pontuados" (score NULL ou
status NOVO) e o erro claro quando não há nada para reprocessar.
"""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.db.models import Campaign, Job, Lead
from src.routes.campaigns import reanalyze_campaign


class _FakeQuery:
    def __init__(self, campaign, lead_count):
        self.campaign = campaign
        self.lead_count = lead_count

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self.campaign

    def count(self):
        return self.lead_count


class _FakeDb:
    def __init__(self, campaign, lead_count):
        self._campaign = campaign
        self._lead_count = lead_count
        self.added = []
        self.committed = 0

    def query(self, model):
        # A 1ª query é de campaign; a contagem usa a 2ª (Lead).
        if model is Campaign:
            return _FakeQuery(self._campaign, self._lead_count)
        return _FakeQuery(None, self._lead_count)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed += 1

    def refresh(self, _obj):
        return None


def _campaign(lead_count=5):
    return SimpleNamespace(
        id="camp-1",
        organization_id="org-1",
        scoring_template_id=None,
    )


def _request():
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/campaigns/camp-1/reanalyze",
        "headers": [],
        "query_string": b"",
        "server": ("127.0.0.1", 8000),
        "client": ("127.0.0.1", 0),
        "scheme": "http",
        "root_path": "",
        "app": SimpleNamespace(state=SimpleNamespace(limiter=None)),
    }
    return Request(scope)


def _call(db, unscored_only=False):
    return asyncio.run(reanalyze_campaign(
        request=_request(),
        campaign_id="camp-1",
        unscored_only=unscored_only,
        db=db,
        _user=SimpleNamespace(id="u"),
        _org=SimpleNamespace(id="org-1"),
    ))


def test_reanalyze_unscored_only_filtra_e_agenda_job():
    db = _FakeDb(_campaign(), lead_count=3)
    out = _call(db, unscored_only=True)
    assert out["status"] == "queued"
    assert out["leads_to_reanalyze"] == 3
    job = db.added[0]
    assert isinstance(job, Job)
    assert job.payload["reanalyze_only"] is True
    assert job.payload["unscored_only"] is True


def test_reanalyze_completo_nao_marca_unscored():
    db = _FakeDb(_campaign(), lead_count=9)
    out = _call(db, unscored_only=False)
    assert out["leads_to_reanalyze"] == 9
    job = db.added[0]
    assert job.payload["unscored_only"] is False


def test_reanalyze_unscored_sem_nada_para_reprocessar_levanta_400():
    db = _FakeDb(_campaign(), lead_count=0)
    with pytest.raises(HTTPException) as exc:
        _call(db, unscored_only=True)
    assert exc.value.status_code == 400
    assert "não pontuados" in exc.value.detail