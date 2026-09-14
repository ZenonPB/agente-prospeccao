"""Testes unitários determinísticos da paginação e do comando bulk de leads."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from src.routes.leads import (
    BulkLeadsRequest,
    ExecuteBulkLeadsRequest,
    _bulk_payload,
    _decode_lead_cursor,
    _encode_lead_cursor,
    list_leads,
)
from src.services.lead_bulk_command_service import (
    BulkCommandValidation,
    LeadBulkCommandService,
    fingerprint_payload,
    normalize_bulk_payload,
)
from database.models import Lead, LeadStatus, LostReason, OrganizationRole, SalesRole


LEAD_A = uuid.UUID("11111111-1111-4111-8111-111111111111")
LEAD_B = uuid.UUID("22222222-2222-4222-8222-222222222222")
ORG_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def _payload(**overrides):
    payload = {
        "operation": "status",
        "lead_ids": [str(LEAD_A)],
        "status": "RESPONDIDO",
        "lost_reason": None,
        "assigned_to_id": None,
        "expected_updated_at": {},
    }
    payload.update(overrides)
    return payload


def test_bulk_rejeita_campo_fora_da_allowlist_no_dto():
    with pytest.raises(ValidationError):
        BulkLeadsRequest(
            operation="status",
            lead_ids=[str(LEAD_A)],
            status="RESPONDIDO",
            organization_id=str(uuid.uuid4()),
        )


def test_bulk_execute_remove_idempotency_key_do_payload_normalizado():
    body = ExecuteBulkLeadsRequest(
        **_payload(),
        idempotency_key="bulk-request-001",
    )

    assert "idempotency_key" not in _bulk_payload(body)


    token = _encode_lead_cursor(84, LEAD_A)
    assert _decode_lead_cursor(token) == (84, LEAD_A)


def test_cursor_invalido_e_rejeitado():
    with pytest.raises(HTTPException) as error:
        _decode_lead_cursor("cursor-forjado")
    assert error.value.status_code == 400


def test_fingerprint_eh_estavel_para_ordem_do_mapa():
    first = _payload(expected_updated_at={str(LEAD_A): "2026-09-15T12:00:00+00:00"})
    second = dict(first, expected_updated_at={str(LEAD_A): "2026-09-15T09:00:00-03:00"})
    assert fingerprint_payload(first) == fingerprint_payload(second)


def test_fingerprint_ignora_campos_semanticalmente_inalterantes():
    status_payload = _payload(
        assigned_to_id=None,
        lost_reason=None,
        expected_updated_at={str(LEAD_A): "2026-09-15T12:00:00+00:00"},
    )
    equivalent_status_payload = _payload(
        assigned_to_id=str(LEAD_B),
        lost_reason="PRECO",
        expected_updated_at={
            str(LEAD_A): "2026-09-15T09:00:00-03:00",
            str(LEAD_B): "2026-09-15T12:00:00+00:00",
        },
    )
    assert fingerprint_payload(status_payload) == fingerprint_payload(
        equivalent_status_payload
    )

    assign_target = uuid.UUID("66666666-6666-4666-8666-666666666666")
    assign_payload = _payload(
        operation="assign",
        status="RESPONDIDO",
        lost_reason=None,
        assigned_to_id=str(assign_target),
        expected_updated_at={str(LEAD_A): "2026-09-15T12:00:00+00:00"},
    )
    equivalent_assign_payload = _payload(
        operation="assign",
        status="PERDIDO",
        lost_reason="PRECO",
        assigned_to_id=str(assign_target),
        expected_updated_at={
            str(LEAD_A): "2026-09-15T09:00:00-03:00",
            str(LEAD_B): "2026-09-15T12:00:00+00:00",
        },
    )
    assert fingerprint_payload(assign_payload) == fingerprint_payload(
        equivalent_assign_payload
    )


def test_normalizacao_rejeita_limite_e_status_perdido_sem_motivo():
    with pytest.raises(BulkCommandValidation, match="entre 1 e 100"):
        normalize_bulk_payload(_payload(lead_ids=[str(uuid.uuid4())] * 101))
    with pytest.raises(BulkCommandValidation, match="lost_reason"):
        normalize_bulk_payload(_payload(status="PERDIDO"))


class _FakeQuery:
    column_descriptions = [{"entity": Lead}]

    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_criteria):
        return self

    def all(self):
        return self.rows


class _FakeDB:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return _FakeQuery(self.rows if model is Lead else [])


def _member(sales_role=SalesRole.MANAGER):
    return SimpleNamespace(
        user_id=uuid.UUID("33333333-3333-4333-8333-333333333333"),
        organization_id=ORG_A,
        role=OrganizationRole.MEMBER,
        sales_role=sales_role,
    )


def _lead(lead_id, *, org_id=ORG_A, assigned_to_id=None, updated_at=None):
    return SimpleNamespace(
        id=lead_id,
        organization_id=org_id,
        assigned_to_id=assigned_to_id,
        updated_at=updated_at,
        status=LeadStatus.NOVO,
        lost_reason=None,
    )


def test_plano_aplica_tenant_scope_e_version_antes_de_aceitar(monkeypatch):
    visible = _lead(LEAD_A, updated_at=datetime(2026, 9, 15, 12, tzinfo=timezone.utc))
    foreign = _lead(LEAD_B, org_id=uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"))
    monkeypatch.setattr(
        "src.services.lead_bulk_command_service.consultant_lead_scope",
        lambda _member, query: query,
    )
    service = LeadBulkCommandService(_FakeDB([visible]), ORG_A, _member(), SimpleNamespace(id=uuid.uuid4()))
    plan = service.preview(_payload(
        lead_ids=[str(LEAD_A), str(LEAD_B)],
        expected_updated_at={str(LEAD_A): "2026-09-15T11:00:00Z"},
    ))
    assert foreign.id not in plan["current_versions"]
    assert plan["accepted_ids"] == []
    assert {item["id"]: item["reason"] for item in plan["rejected"]} == {
        str(LEAD_A): "VERSION_CONFLICT",
        str(LEAD_B): "NOT_FOUND_OR_UNAUTHORIZED",
    }
    assert visible.status == LeadStatus.NOVO
    assert visible.lost_reason is None


def test_plano_rejeita_lead_sem_versao_mesmo_sem_expected_e_nao_muta():
    lead = _lead(LEAD_A)
    service = LeadBulkCommandService(
        _FakeDB([lead]), ORG_A, _member(), SimpleNamespace(id=uuid.uuid4())
    )

    plan = service.preview(_payload(expected_updated_at={}))

    assert plan["accepted_ids"] == []
    assert plan["rejected"] == [{"id": str(LEAD_A), "reason": "VERSION_CONFLICT"}]
    assert plan["current_versions"] == {str(LEAD_A): None}
    assert lead.status == LeadStatus.NOVO
    assert lead.lost_reason is None
    assert lead.assigned_to_id is None
    assert lead.updated_at is None


@pytest.mark.parametrize(
    ("status", "lost_reason", "outcome"),
    [
        (LeadStatus.RESPONDIDO, None, "RESPONDED"),
        (LeadStatus.REUNIAO_MARCADA, None, "MEETING"),
        (LeadStatus.REUNIAO_FEITA, None, "MEETING"),
        (LeadStatus.PERDIDO, LostReason.PRECO, "LOST"),
    ],
)
def test_apply_status_usa_transicao_canonica_e_registra_outcome(
    monkeypatch, status, lost_reason, outcome
):
    lead = _lead(LEAD_A)
    db = SimpleNamespace()
    service = LeadBulkCommandService(
        db, ORG_A, _member(), SimpleNamespace(id=uuid.uuid4())
    )
    activity = SimpleNamespace(id=uuid.UUID("55555555-5555-4555-8555-555555555555"))
    transition_calls = []
    outcome_calls = []

    def fake_transition(db_arg, lead_arg, status_arg, **kwargs):
        transition_calls.append((db_arg, lead_arg, status_arg, kwargs))
        lead_arg.status = status_arg
        lead_arg.lost_reason = kwargs.get("lost_reason")
        return activity

    class FakeOutcomeService:
        def record_for_lead(self, db_arg, organization_id, lead_id, **kwargs):
            outcome_calls.append((db_arg, organization_id, lead_id, kwargs))

    monkeypatch.setattr(
        "src.services.lead_bulk_command_service.transition_lead_status",
        fake_transition,
    )
    from services.prospecting import commercial_outcome_service

    monkeypatch.setattr(
        commercial_outcome_service,
        "CommercialOutcomeService",
        FakeOutcomeService,
    )

    changed, reason = service._apply_status(
        lead,
        _payload(status=status.value, lost_reason=lost_reason.value if lost_reason else None),
    )

    assert (changed, reason) == (True, None)
    assert transition_calls == [
        (
            db,
            lead,
            status,
            {"user_id": str(service.user_id), "lost_reason": lost_reason},
        )
    ]
    assert outcome_calls == [
        (
            db,
            ORG_A,
            LEAD_A,
            {
                "outcome": outcome,
                "event_key": f"activity:{activity.id}",
            },
        )
    ]


def test_apply_status_duplicate_nao_chama_transicao(monkeypatch):
    lead = _lead(LEAD_A)
    lead.status = LeadStatus.RESPONDIDO
    service = LeadBulkCommandService(
        SimpleNamespace(), ORG_A, _member(), SimpleNamespace(id=uuid.uuid4())
    )
    monkeypatch.setattr(
        "src.services.lead_bulk_command_service.transition_lead_status",
        lambda *_args, **_kwargs: pytest.fail("transição não deve ocorrer para duplicata"),
    )

    assert service._apply_status(lead, _payload(status="RESPONDIDO")) == (
        False,
        "ALREADY_IN_DESIRED_STATE",
    )


def test_plano_rejeita_consultor_fora_da_carteira(monkeypatch):
    other_user = uuid.UUID("44444444-4444-4444-8444-444444444444")
    current = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)
    lead = _lead(
        LEAD_A,
        assigned_to_id=other_user,
        updated_at=current,
    )
    monkeypatch.setattr(
        "src.services.lead_bulk_command_service.consultant_lead_scope",
        lambda _member, query: query,
    )
    service = LeadBulkCommandService(
        _FakeDB([lead]), ORG_A, _member(SalesRole.CONSULTOR), SimpleNamespace(id=uuid.uuid4())
    )
    expected = {str(LEAD_A): current.isoformat()}
    plan = service.preview(_payload(expected_updated_at=expected))
    assert plan["accepted_ids"] == [str(LEAD_A)]
    # O helper de escopo normalmente remove o lead antes; este teste cobre a
    # defesa adicional do plano quando um query customizado devolve carteira alheia.
    service = LeadBulkCommandService(
        _FakeDB([lead]), ORG_A, _member(SalesRole.CONSULTOR), SimpleNamespace(id=uuid.uuid4())
    )
    plan = service._plan(dict(_payload(operation="assign", assigned_to_id=None, expected_updated_at=expected)))
    assert plan["rejected"][0]["reason"] == "NOT_AUTHORIZED"


class _LeadListQuery:
    def __init__(self):
        self.filters = []

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def count(self):
        return 0

    def order_by(self, *ordering):
        return self

    def options(self, *options):
        return self

    def offset(self, value):
        return self

    def limit(self, value):
        return self

    def all(self):
        return []


class _LeadListDB:
    def __init__(self):
        self.query_instance = None

    def query(self, model):
        self.query_instance = _LeadListQuery()
        return self.query_instance


def _call_list_leads(db, **overrides):
    params = {
        "status": None,
        "campaign_id": None,
        "search": None,
        "min_score": None,
        "assigned": None,
        "consultant_id": None,
        "next_action_before": None,
        "priority": None,
        "limit": 50,
        "offset": 0,
        "cursor": None,
        "db": db,
        "_user": SimpleNamespace(id=uuid.uuid4()),
        "_org": SimpleNamespace(id=ORG_A),
        "member": _member(),
    }
    params.update(overrides)
    return list_leads(**params)


def test_cursor_nulo_inclui_scores_preenchidos_apos_desempate(monkeypatch):
    monkeypatch.setattr("src.routes.leads.consultant_lead_scope", lambda _member, query: query)
    db = _LeadListDB()

    _call_list_leads(db, cursor=_encode_lead_cursor(None, LEAD_A))

    cursor_filter = db.query_instance.filters[-1]
    compiled = str(cursor_filter.compile(dialect=postgresql.dialect()))
    assert "qualification_score IS NULL" in compiled
    assert "qualification_score IS NOT NULL" in compiled
    assert "id >" in compiled
    assert " OR " in compiled


def test_cursor_com_offset_diferente_de_zero_e_rejeitado():
    with pytest.raises(HTTPException) as error:
        _call_list_leads(
            _LeadListDB(),
            cursor=_encode_lead_cursor(84, LEAD_A),
            offset=1,
        )

    assert error.value.status_code == 400
    assert error.value.detail == "offset não pode ser combinado com cursor"
