"""Regressão do feedback de score (loop de aprendizado da IA).

POST /api/leads/{lead_id}/score-feedback: corrige o score do lead (respeitando
a regra >= 60 → QUALIFICADO), registra na trilha de atividades e cria o
ScoringFeedback como insumo do loop de calibração (Fase 1 —
docs/ai-feedback-loop.md).
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.routes.score_feedback import (
    ScoreFeedbackRequest,
    _direction,
    create_score_feedback,
)
from src.db.models import FeedbackDirection, Lead, LeadStatus


class _FakeCampaign:
    def __init__(self):
        self.scoring_template_id = "tmpl-1"


class _FakeLead:
    def __init__(self, score=85, status=LeadStatus.ANALISADO):
        self.id = "lead-1"
        self.organization_id = "org-1"
        self.campaign_id = "camp-1"
        self.campaign = _FakeCampaign()
        self.qualification_score = score
        self.status = status


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._all = None

    def filter(self, *a, **k):
        return self

    def all(self):
        return self._rows if self._all is None else self._all

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDB:
    def __init__(self, lead):
        self.lead = lead
        self.added = []
        self.commits = 0

    def query(self, model):
        if model is Lead:
            return _FakeQuery([self.lead])
        row = SimpleNamespace(id="l1", company_name="x")
        return _FakeQuery([row])

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1


class _User:
    id = "user-1"


class _Org:
    id = "org-1"


def _call(db, score=40, reason="site atualizado e bonito, nao e uma dor", assert_apply=True):
    return create_score_feedback(
        lead_id="lead-1",
        body=ScoreFeedbackRequest(
            suggested_score=score, reason=reason, apply_to_lead=assert_apply,
        ),
        db=db,
        user=_User(),
        org=_Org(),
    )


def test_feedback_corrige_score_e_reclassifica_para_desqualificado():
    lead = _FakeLead(score=85, status=LeadStatus.ANALISADO)
    db = _FakeDB(lead)
    resp = _call(db, score=40)

    assert lead.qualification_score == 40
    assert lead.status == LeadStatus.DESQUALIFICADO
    assert resp.direction == "MUITO_ALTO"
    assert resp.applied_to_lead is True
    # Score corrigido + motivo na trilha
    activity = next(a for a in db.added if hasattr(a, "action") and a.action.value == "SCORE_FEEDBACK")
    assert "85 → 40" in activity.detail
    assert "site atualizado" in activity.detail
    # Feedback persistido com relações
    fb = None
    for a in db.added:
        if getattr(a, 'original_score', None) is not None:
            fb = a
            break
    assert fb is not None
    assert fb.original_score == 85
    assert fb.suggested_score == 40
    assert fb.campaign_id == "camp-1"
    assert fb.template_id == "tmpl-1"
    assert db.commits == 1


def test_feedback_nao_reclassifica_depois_de_contatado():
    lead = _FakeLead(score=85, status=LeadStatus.CONTATADO)
    db = _FakeDB(lead)
    resp = _call(db, score=40)

    assert lead.status == LeadStatus.CONTATADO  # histórico: não reclassifica
    assert lead.qualification_score == 40
    assert resp.lead_status == "CONTATADO"


def test_direction_muito_baixo_quando_o_consultor_acha_excelente():
    lead = _FakeLead(score=45, status=LeadStatus.ANALISADO)
    db = _FakeDB(lead)
    resp = _call(db, score=80)

    assert lead.qualification_score == 80
    assert lead.status == LeadStatus.QUALIFICADO
    assert resp.direction == "MUITO_BAIXO"


def test_feedback_rejeita_score_igual():
    db = _FakeDB(_FakeLead(score=50))
    with pytest.raises(HTTPException) as exc:
        _call(db, score=50)
    assert exc.value.status_code == 422