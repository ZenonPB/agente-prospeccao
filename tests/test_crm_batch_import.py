"""Testes do endpoint de importação em lote do CRM Paste.

Sem banco real: `get_db` e `get_user_membership` são sobrescritos com fakes
(FakeDB grava os objetos adicionados; dedupe é simulado por `results`).
"""
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routes import crm


def _make_client(contact_results=None, campaign_results=None):
    """App de teste com dependências de auth/DB substituídas por fakes."""
    app = FastAPI()
    app.include_router(crm.router)

    org_id = uuid.uuid4()
    org = SimpleNamespace(id=org_id)
    member = SimpleNamespace(organization_id=org_id, organization=org)

    added = []

    class FakeQuery:
        def __init__(self, model):
            self.model = model

        def join(self, *a, **k):
            return self

        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def first(self):
            if self.model.__name__ == "Contact":
                return (contact_results or [None])[0]
            if self.model.__name__ == "Campaign":
                return (campaign_results or [None])[0]
            return None

        def all(self):
            return []

    class FakeDB:
        def query(self, model):
            return FakeQuery(model)

        def add(self, obj):
            added.append(obj)

        def flush(self):
            pass

        def commit(self):
            pass

        def rollback(self):
            pass

    fake_db = FakeDB()

    app.dependency_overrides[crm.get_db] = lambda: fake_db
    app.dependency_overrides[crm.get_user_membership] = lambda: member
    return TestClient(app, raise_server_exceptions=False), added


def _item(**overrides):
    base = {"lead": "Fabio Prada Perez", "empresa": "Clinica Maua",
            "pitch_enviado": True, "pitch_data": "2026-08-03",
            "respondeu": "NÃO"}
    base.update(overrides)
    return base


def test_batch_import_insere_lead_contact_e_followups():
    client, added = _make_client()
    resp = client.post("/crm/batch-import", json={"items": [_item()]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["inserted"] == 1
    assert data["duplicates"] == 0

    from src.db.models import Contact, FollowUp, Lead
    leads = [o for o in added if isinstance(o, Lead)]
    contacts = [o for o in added if isinstance(o, Contact)]
    followups = [o for o in added if isinstance(o, FollowUp)]
    assert len(leads) == 1
    assert leads[0].company_name == "Clinica Maua"
    # respondeu="NÃO" mas pitch enviado → CONTATADO (SIM viraria RESPONDIDO)
    assert leads[0].status.name == "CONTATADO"
    assert len(contacts) == 1
    assert contacts[0].name == "Fabio Prada Perez"
    assert contacts[0].is_primary is True
    # pitch (OPENING, sent) + 3 follow-ups pendentes
    assert len(followups) == 4
    sent = [f for f in followups if f.status.name == "SENT"]
    assert len(sent) == 1 and sent[0].step.name == "OPENING"


def test_batch_import_detecta_duplicata():
    existing = SimpleNamespace(lead_id=uuid.uuid4(), name="Fabio Prada Perez")
    client, added = _make_client(contact_results=[existing])
    resp = client.post("/crm/batch-import", json={"items": [_item()]})
    assert resp.status_code == 200
    assert resp.json()["duplicates"] == 1
    assert resp.json()["inserted"] == 0
    assert added == []


def test_batch_import_campanha_inexistente_retorna_404():
    client, _ = _make_client()
    resp = client.post("/crm/batch-import", json={
        "items": [_item()], "campaign_id": str(uuid.uuid4()),
    })
    assert resp.status_code == 404


def test_batch_import_sem_itens_nem_texto_retorna_422():
    client, _ = _make_client()
    resp = client.post("/crm/batch-import", json={})
    assert resp.status_code == 422


def test_batch_import_consultant_invalido_retorna_422():
    client, _ = _make_client()
    resp = client.post("/crm/batch-import", json={
        "items": [_item()], "consultant_user_id": "nao-e-uuid",
    })
    assert resp.status_code == 422
