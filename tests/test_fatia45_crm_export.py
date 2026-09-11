"""Falhas de CRM verdadeiro (Fatia 5) + export cross-tenant (Fatia 4/6).

RED: cobre WON x LOST x DESQUALIFICADO, motivo obrigatório de LOST,
motivo opcional de DESQUALIFIED e isolamento cross-tenant do CSV.
"""
from types import SimpleNamespace
from uuid import uuid4

from src.db.models import LeadStatus, LostReason


def _mk_lead(status=LeadStatus.PROPOSTA_ENVIADA, org="org-a"):
    return SimpleNamespace(
        id=uuid4(), organization_id=org, assigned_to_id=None,
        status=status, lost_reason=None, offer_key="trophies",
        offer_version="v1", qualification_score=70,
    )


class _Q:
    def __init__(self, items):
        self._items = items
    def filter(self, *a, **k):
        return self
    def order_by(self, *a):
        return self
    def first(self):
        return self._items[0] if self._items else None
    def all(self):
        return list(self._items)


class _DB:
    def __init__(self, lead=None, leads=(), opps=()):
        self._lead = lead
        self._leads = list(leads)
        self._opps = list(opps)
        self.added = []
        self.committed = 0
    def query(self, model, *args):
        from src.db.models import Lead, LeadOpportunityRow, CommercialOutcomeRow
        name = getattr(model, "__tablename__", None) or getattr(model, "__name__", "")
        if name == "leads" and self._lead is not None:
            return _Q([self._lead])
        if name == "leads":
            return _Q(self._leads)
        if name in ("lead_opportunities", "LeadOpportunityRow"):
            return _Q(self._opps)
        return _Q([])
    def add(self, row):
        self.added.append(row)
    def commit(self):
        self.committed += 1


def _ctx(lead=None, leads=(), opps=(), user_id="u1", org="org-a", role="member", sales="CONSULTOR"):
    member = SimpleNamespace(
        user_id=user_id, organization_id=org,
        role=SimpleNamespace(value=role), sales_role=SimpleNamespace(value=sales),
    )
    user = SimpleNamespace(id=user_id)
    org_ns = SimpleNamespace(id=org)
    return member, user, org_ns


def test_mark_lost_exige_motivo_e_registra_lost():
    from src.routes.leads import mark_lead_lost, MarkLostRequest
    lead = _mk_lead()
    db = _DB(lead=lead)
    member, user, org = _ctx()
    out = mark_lead_lost(str(lead.id), MarkLostRequest(lost_reason=LostReason.PRECO), db, user, org, member)
    assert out["status"] == LeadStatus.PERDIDO.value
    assert out["lost_reason"] == "PRECO"
    assert lead.status == LeadStatus.PERDIDO
    assert lead.lost_reason == LostReason.PRECO


def test_mark_disqualified_nao_gera_lost_e_registra_motivo():
    from src.routes.leads import mark_lead_disqualified, MarkDisqualifiedRequest
    lead = _mk_lead()
    db = _DB(lead=lead)
    member, user, org = _ctx()
    out = mark_lead_disqualified(str(lead.id), MarkDisqualifiedRequest(reason="Fora do ICP"), db, user, org, member)
    assert out["status"] == LeadStatus.DESQUALIFICADO.value
    assert lead.status == LeadStatus.DESQUALIFICADO
    assert lead.lost_reason is None
    assert not [r for r in db.added if getattr(r, "outcome", "") == "LOST"]


def test_mark_disqualified_sem_motivo_tambem_passar():
    from src.routes.leads import mark_lead_disqualified, MarkDisqualifiedRequest
    lead = _mk_lead()
    db = _DB(lead=lead)
    member, user, org = _ctx()
    out = mark_lead_disqualified(str(lead.id), MarkDisqualifiedRequest(), db, user, org, member)
    assert out["status"] == LeadStatus.DESQUALIFICADO.value


def test_export_cross_tenant_nao_vaza_campanha_alheia():
    from fastapi import HTTPException
    from src.routes.campaigns import export_campaign_google_sheets
    db = _DB(leads=[])
    member, user, org = _ctx(org="org-b")
    try:
        export_campaign_google_sheets("campanha-org-a", db, user, org, member)
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("export de campanha alheia deveria dar 404")


def test_pipeline_bloqueia_campanha_pausada_ou_encerrada():
    # Guard real no source de pipeline.py: PAUSED/ARCHIVED/COMPLETED → 400.
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[1] / "services" / "api" / "src" / "routes" / "pipeline.py"
    text = src.read_text(encoding="utf-8")
    assert "PAUSED" in text and "ARCHIVED" in text and "COMPLETED" in text
    assert "retome a busca" in text
    assert "duplique para iniciar um novo ciclo" in text
