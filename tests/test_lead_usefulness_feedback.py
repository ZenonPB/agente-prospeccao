"""Feedback de utilidade do lead (👍 útil / 👎 não útil).

Seam pública sob teste: `create_usefulness_feedback` em
`src.routes.lead_usefulness` (POST /leads/{id}/usefulness-feedback).

Regras:
- org-scoped: lead de outra org → 404 (teste negativo cross-tenant);
- útil=True não exige motivo; útil=False exige motivo da taxonomia;
- motivo fora da taxonomia → 422;
- idempotente por (lead, usuário): segundo envio atualiza, não duplica;
- registra trilha LEAD_FEEDBACK auditável.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.routes.lead_usefulness import (
    UsefulnessFeedbackRequest,
    create_usefulness_feedback,
)
from src.db.models import LeadStatus


class _FakeLead:
    def __init__(self, org="org-1"):
        self.id = "lead-1"
        self.organization_id = org
        self.campaign_id = "camp-1"
        self.status = LeadStatus.ANALISADO


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDB:
    def __init__(self, lead, feedbacks=None):
        self.lead = lead
        self.feedbacks = list(feedbacks or [])
        self.added = []
        self.commits = 0

    def query(self, model):
        from src.db.models import Lead, LeadUsefulnessFeedback
        if model is Lead:
            # O filtro org-scoped real é por SQL; o fake respeita a org ativa.
            if self.lead is not None and str(self.lead.organization_id) != "org-1":
                return _FakeQuery([])
            return _FakeQuery([self.lead] if self.lead else [])
        if model is LeadUsefulnessFeedback:
            return _FakeQuery(list(self.feedbacks))
        return _FakeQuery([])

    def add(self, obj):
        # Simula upsert: se já existe feedback do mesmo usuário no lead,
        # o caller atualiza o objeto existente em vez de adicionar outro.
        self.added.append(obj)

    def commit(self):
        self.commits += 1


class _User:
    id = "user-1"


class _Org:
    id = "org-1"


def _call(db, useful=True, reason=None, detail=None, lead_id="lead-1"):
    return create_usefulness_feedback(
        lead_id=lead_id,
        body=UsefulnessFeedbackRequest(useful=useful, reason=reason, detail=detail),
        db=db,
        user=_User(),
        org=_Org(),
    )


def test_feedback_util_registra_sem_motivo():
    db = _FakeDB(_FakeLead())
    resp = _call(db, useful=True)
    assert resp.useful is True
    assert resp.lead_id == "lead-1"
    assert db.commits == 1
    fb = next(a for a in db.added if getattr(a, "useful", None) is True)
    assert str(fb.organization_id) == "org-1"
    assert str(fb.lead_id) == "lead-1"


def test_feedback_nao_util_exige_motivo():
    db = _FakeDB(_FakeLead())
    with pytest.raises(HTTPException) as exc:
        _call(db, useful=False, reason=None)
    assert exc.value.status_code == 422


def test_feedback_nao_util_com_motivo_valido():
    db = _FakeDB(_FakeLead())
    resp = _call(db, useful=False, reason="SEM_NECESSIDADE", detail="Sem verba no semestre")
    assert resp.useful is False
    assert resp.reason == "SEM_NECESSIDADE"


def test_feedback_motivo_invalido_rejeitado():
    db = _FakeDB(_FakeLead())
    with pytest.raises(HTTPException) as exc:
        _call(db, useful=False, reason="MOTIVO_INVENTADO")
    assert exc.value.status_code == 422


def test_feedback_cross_tenant_retorna_404():
    db = _FakeDB(_FakeLead(org="org-outra"))
    with pytest.raises(HTTPException) as exc:
        _call(db, useful=True)
    assert exc.value.status_code == 404


def test_feedback_idempotente_atualiza_mesmo_usuario():
    existing = SimpleNamespace(
        id="fb-1", lead_id="lead-1", user_id="user-1",
        organization_id="org-1", useful=True, reason=None, detail=None,
    )
    db = _FakeDB(_FakeLead(), feedbacks=[existing])
    resp = _call(db, useful=False, reason="CONTATO_ERRADO")
    assert resp.useful is False
    # Não cria segunda linha para o mesmo (lead, usuário).
    created = [a for a in db.added if getattr(a, "useful", None) is False and getattr(a, "id", None) != "fb-1"]
    assert created == []
    assert existing.useful is False
    assert existing.reason.value == "CONTATO_ERRADO"
