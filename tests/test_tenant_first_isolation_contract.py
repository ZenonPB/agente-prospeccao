"""Provas determinísticas do contrato tenant-first da Task 1.2.

As consultas usam os predicados SQLAlchemy reais sobre ``sqlalchemy_memory``.
Assim, as linhas dos dois workspaces permanecem no harness e o filtro de
produção, não o fixture, decide o que é visível. Nenhum provider ou Postgres
real é necessário nestes testes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException

from sqlalchemy_memory import ConsultaMemoria
from src.auth.dependencies import get_organization_context
from src.db.models import (
    Campaign,
    ImportJob,
    ImportRowResult,
    Lead,
    LeadOpportunityRow,
    Organization,
    OrganizationMember,
    OrganizationRole,
    SalesRole,
)
from src.routes.leads import list_leads
from src.services.import_job_service import ImportJobError, create_preview, list_rows, process_import_job
from src.services.lead_bulk_command_service import LeadBulkCommandService
from src.services.opportunity_command_service import OpportunityCommandService, OpportunityNotFound
from src.services.org_service import consultant_lead_scope


ORG_A = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
ORG_B = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
USER_A = uuid.UUID("11111111-1111-4111-8111-111111111111")
USER_B = uuid.UUID("22222222-2222-4222-8222-222222222222")
LEAD_B = uuid.UUID("33333333-3333-4333-8333-333333333333")
OPPORTUNITY_B = uuid.UUID("44444444-4444-4444-8444-444444444444")
IMPORT_B = uuid.UUID("55555555-5555-4555-8555-555555555555")
CAMPAIGN_B = uuid.UUID("66666666-6666-4666-8666-666666666666")


def _member(org_id=ORG_A, user_id=USER_A, sales_role=SalesRole.MANAGER):
    return SimpleNamespace(
        organization_id=org_id,
        user_id=user_id,
        role=OrganizationRole.MEMBER,
        sales_role=sales_role,
    )



class _LeadQuery(ConsultaMemoria):
    """Subconjunto de paginação usado pela rota real de leads."""

    def __init__(self, table, rows):
        super().__init__(table, rows)
        self._offset = 0
        self._limit = None

    def count(self):
        return len(self._selecionadas())

    def options(self, *_args, **_kwargs):
        return self

    def offset(self, value):
        self._offset = value
        return self

    def limit(self, value):
        self._limit = value
        return self

    def all(self):
        rows = self._selecionadas()
        end = None if self._limit is None else self._offset + self._limit
        return rows[self._offset:end]


def _query_db(rows_by_model):
    """Cria uma sessão somente-leitura que avalia filtros SQLAlchemy reais."""

    class _DB:
        def __init__(self):
            self.query_models = []
            self.added = []
            self.commits = 0

        def query(self, model, *_args):
            self.query_models.append(model)
            if model not in rows_by_model:
                raise AssertionError(f"consulta inesperada no teste: {model}")
            table, rows = rows_by_model[model]
            query_type = _LeadQuery if model is Lead else ConsultaMemoria
            return query_type(table, rows)

        def add(self, item):
            self.added.append(item)

        def commit(self):
            self.commits += 1
            raise AssertionError("operação cross-tenant não pode fazer commit")

        def flush(self):
            raise AssertionError("operação cross-tenant não pode fazer flush")

        def close(self):
            return None

    return _DB()


def _row(table, entity):
    return {table: entity}


def _lead(lead_id, organization_id, *, assigned_to_id=None):
    return SimpleNamespace(
        id=lead_id,
        organization_id=organization_id,
        assigned_to_id=assigned_to_id,
        updated_at=datetime(2026, 9, 15, 12, tzinfo=timezone.utc),
        status="NOVO",
        lost_reason=None,
        qualification_score=None,
    )


def _request(organization_id):
    return SimpleNamespace(headers={"X-Organization-Id": str(organization_id)})


def test_contexto_rejeita_workspace_sem_membership_antes_de_carregar_organization():
    """Um header com UUID conhecido de B não troca o workspace de A."""
    membership_a = SimpleNamespace(
        organization_id=ORG_A,
        user_id=USER_A,
        role=OrganizationRole.MEMBER,
        sales_role=SalesRole.CONSULTOR,
    )
    db = _query_db({
        OrganizationMember: (
            "organization_members",
            [_row("organization_members", membership_a)],
        ),
        Organization: ("organizations", []),
    })

    with pytest.raises(HTTPException) as error:
        get_organization_context(
            user=SimpleNamespace(id=USER_A),
            db=db,
            request=_request(ORG_B),
        )

    assert error.value.status_code == 403
    assert db.query_models == [OrganizationMember]
    assert db.added == []
    assert db.commits == 0


def test_consultor_ve_propria_carteira_e_pool_sem_ver_colega_ou_outro_tenant():
    own = _lead(uuid.uuid4(), ORG_A, assigned_to_id=USER_A)
    pool = _lead(uuid.uuid4(), ORG_A)
    colleague = _lead(uuid.uuid4(), ORG_A, assigned_to_id=USER_B)
    foreign_pool = _lead(LEAD_B, ORG_B)
    db = _query_db({
        Lead: (
            "leads",
            [_row("leads", row) for row in (foreign_pool, colleague, pool, own)],
        ),
    })

    visible = consultant_lead_scope(_member(sales_role=SalesRole.CONSULTOR), db.query(Lead)).all()

    assert {item.id for item in visible} == {own.id, pool.id}
    assert colleague.id not in {item.id for item in visible}
    assert foreign_pool.id not in {item.id for item in visible}


def test_rota_de_leads_nao_retorna_uuid_conhecido_de_outro_workspace():
    foreign = _lead(LEAD_B, ORG_B, assigned_to_id=USER_B)
    db = _query_db({Lead: ("leads", [_row("leads", foreign)])})

    result = list_leads(
        db=db,
        _user=SimpleNamespace(id=USER_A),
        _org=SimpleNamespace(id=ORG_A),
        member=_member(sales_role=SalesRole.MANAGER),
        assigned=None,
        priority=None,
        limit=50,
        offset=0,
    )

    assert result["total"] == 0
    assert result["leads"] == []
    assert db.added == []
    assert db.commits == 0


def test_import_get_e_rows_falham_fechado_sem_ler_linhas_de_outro_workspace():
    foreign_job = SimpleNamespace(id=IMPORT_B, organization_id=ORG_B)
    db = _query_db({ImportJob: ("import_jobs", [_row("import_jobs", foreign_job)])})

    with pytest.raises(ImportJobError) as error:
        list_rows(db, ORG_A, IMPORT_B)

    assert error.value.status_code == 404
    assert error.value.code == "IMPORT_NOT_FOUND"
    assert db.query_models == [ImportJob]
    assert ImportRowResult not in db.query_models
    assert db.added == []
    assert db.commits == 0


def test_import_nao_cria_job_para_campanha_uuid_de_outro_workspace():
    foreign_campaign = SimpleNamespace(id=CAMPAIGN_B, organization_id=ORG_B)
    db = _query_db({Campaign: ("campaigns", [_row("campaigns", foreign_campaign)])})

    with pytest.raises(ImportJobError) as error:
        create_preview(
            db,
            ORG_A,
            USER_A,
            b"Nome\nEmpresa\n",
            "historico.csv",
            "text/csv",
            campaign_id=CAMPAIGN_B,
        )

    assert error.value.status_code == 404
    assert error.value.code == "CAMPAIGN_NOT_FOUND"
    assert db.added == []
    assert db.commits == 0


def test_worker_de_import_falha_antes_de_processar_job_de_outro_workspace(monkeypatch):
    foreign_job = SimpleNamespace(id=IMPORT_B, organization_id=ORG_B, status="RUNNING")
    db = _query_db({ImportJob: ("import_jobs", [_row("import_jobs", foreign_job)])})
    monkeypatch.setattr("src.db.session.SessionLocal", lambda: db)

    process_import_job(str(IMPORT_B), str(ORG_A))

    assert db.query_models == [ImportJob]
    assert ImportRowResult not in db.query_models
    assert db.added == []
    assert db.commits == 0


def test_bulk_preview_rejeita_uuid_conhecido_de_outro_workspace_sem_mutar():
    foreign = _lead(LEAD_B, ORG_B, assigned_to_id=USER_B)
    db = _query_db({Lead: ("leads", [_row("leads", foreign)])})
    service = LeadBulkCommandService(db, ORG_A, _member(), SimpleNamespace(id=USER_A))

    result = service.preview({
        "operation": "status",
        "lead_ids": [str(LEAD_B)],
        "status": "RESPONDIDO",
        "lost_reason": None,
        "assigned_to_id": None,
        "expected_updated_at": {str(LEAD_B): foreign.updated_at.isoformat()},
    })

    assert result["accepted_ids"] == []
    assert result["rejected"] == [{"id": str(LEAD_B), "reason": "NOT_FOUND_OR_UNAUTHORIZED"}]
    assert db.added == []
    assert db.commits == 0


def test_opportunity_command_rejeita_uuid_de_outro_workspace_antes_de_mutar():
    foreign = SimpleNamespace(
        id=OPPORTUNITY_B,
        organization_id=ORG_B,
        lead_id=LEAD_B,
    )
    db = _query_db({
        LeadOpportunityRow: (
            "lead_opportunities",
            [_row("lead_opportunities", foreign)],
        ),
    })
    service = OpportunityCommandService(
        db,
        ORG_A,
        _member(),
        SimpleNamespace(id=USER_A),
    )

    with pytest.raises(OpportunityNotFound):
        service.update(OPPORTUNITY_B, {"value": 1500})

    assert db.query_models == [LeadOpportunityRow]
    assert db.added == []
    assert db.commits == 0
