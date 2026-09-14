"""Testes determinísticos do contrato de estados do Import Job."""
from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from src.db.models import ImportJobStatus, OrganizationRole, SalesRole
from src.services.import_job_service import (
    ImportJobError,
    _ALLOWED_TRANSITIONS,
    _transition,
)


ORG_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
ACTOR_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
OTHER_ACTOR_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")


class _AuditDb:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)


def _job(status: ImportJobStatus, *, actor_id=ACTOR_ID, version=1):
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=ORG_ID,
        actor_id=actor_id,
        status=status,
        expected_version=version,
        correlation_id="corr-import-test",
    )


def _member(*, user_id=ACTOR_ID, sales_role=SalesRole.MANAGER, role=OrganizationRole.MEMBER):
    return SimpleNamespace(
        organization_id=ORG_ID,
        user_id=user_id,
        sales_role=sales_role,
        role=role,
    )


def test_tabela_de_transicoes_cobre_todos_os_estados_do_contrato():
    assert set(_ALLOWED_TRANSITIONS) == set(ImportJobStatus)
    assert _ALLOWED_TRANSITIONS[ImportJobStatus.DRAFT] == frozenset({ImportJobStatus.PREVIEWED, ImportJobStatus.CANCELLED})
    assert _ALLOWED_TRANSITIONS[ImportJobStatus.PREVIEWED] == frozenset({ImportJobStatus.DRAFT, ImportJobStatus.QUEUED, ImportJobStatus.CANCELLED})
    assert _ALLOWED_TRANSITIONS[ImportJobStatus.QUEUED] == frozenset({ImportJobStatus.RUNNING, ImportJobStatus.CANCEL_REQUESTED})
    assert _ALLOWED_TRANSITIONS[ImportJobStatus.RUNNING] == frozenset({
        ImportJobStatus.SUCCEEDED,
        ImportJobStatus.PARTIAL,
        ImportJobStatus.FAILED,
        ImportJobStatus.CANCEL_REQUESTED,
    })
    assert _ALLOWED_TRANSITIONS[ImportJobStatus.PARTIAL] == frozenset({ImportJobStatus.QUEUED})
    assert _ALLOWED_TRANSITIONS[ImportJobStatus.FAILED] == frozenset({ImportJobStatus.QUEUED})
    assert _ALLOWED_TRANSITIONS[ImportJobStatus.CANCEL_REQUESTED] == frozenset({ImportJobStatus.CANCELLED})
    assert _ALLOWED_TRANSITIONS[ImportJobStatus.SUCCEEDED] == frozenset()
    assert _ALLOWED_TRANSITIONS[ImportJobStatus.CANCELLED] == frozenset()


def test_transicao_valida_incrementa_versao_e_persiste_auditoria_com_actor():
    db = _AuditDb()
    job = _job(ImportJobStatus.DRAFT)

    _transition(
        db,
        job,
        ImportJobStatus.PREVIEWED,
        actor_id=ACTOR_ID,
        expected_version=1,
        member=_member(),
    )

    assert job.status is ImportJobStatus.PREVIEWED
    assert job.expected_version == 2
    assert len(db.added) == 1
    audit = db.added[0]
    assert audit.organization_id == ORG_ID
    assert audit.actor_id == ACTOR_ID
    assert audit.from_status == "DRAFT"
    assert audit.to_status == "PREVIEWED"


def test_transicao_rejeita_versao_obsoleta_sem_mutar_nem_auditar():
    db = _AuditDb()
    job = _job(ImportJobStatus.PREVIEWED, version=4)

    with pytest.raises(ImportJobError, match="desatualizada") as error:
        _transition(
            db,
            job,
            ImportJobStatus.QUEUED,
            actor_id=ACTOR_ID,
            expected_version=3,
            member=_member(),
        )

    assert error.value.code == "VERSION_CONFLICT"
    assert job.status is ImportJobStatus.PREVIEWED
    assert job.expected_version == 4
    assert db.added == []


def test_transicao_rejeita_consultor_em_job_de_outro_actor_e_manager_autorizado():
    db = _AuditDb()
    job = _job(ImportJobStatus.PREVIEWED, actor_id=OTHER_ACTOR_ID)

    with pytest.raises(ImportJobError) as error:
        _transition(
            db,
            job,
            ImportJobStatus.CANCELLED,
            actor_id=ACTOR_ID,
            expected_version=1,
            member=_member(sales_role=SalesRole.CONSULTOR),
        )

    assert error.value.code == "UNAUTHORIZED"
    assert job.status is ImportJobStatus.PREVIEWED
    assert db.added == []

    _transition(
        db,
        job,
        ImportJobStatus.CANCELLED,
        actor_id=ACTOR_ID,
        expected_version=1,
        member=_member(sales_role=SalesRole.MANAGER),
    )
    assert job.status is ImportJobStatus.CANCELLED


def test_estados_terminais_rejeitam_novas_transicoes():
    for terminal in (ImportJobStatus.SUCCEEDED, ImportJobStatus.CANCELLED):
        db = _AuditDb()
        job = _job(terminal)

        with pytest.raises(ImportJobError) as error:
            _transition(
                db,
                job,
                ImportJobStatus.QUEUED,
                actor_id=ACTOR_ID,
                expected_version=1,
                member=_member(),
            )

        assert error.value.code == "STATE_TERMINAL"
        assert job.status is terminal
        assert db.added == []
