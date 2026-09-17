"""Isolamento real do guard por lead (sessão dedicada).

Regressão de `enrichment_orchestrator.py:332`: com o savepoint compartilhando
a sessão do loop, um `db.commit()` no meio da operação (ex.:
`QuotaService.consume` após Groq 200) fechava a transação do contexto e o
próximo toque em atributo expirado levantava
`InvalidRequestError: Can't operate on closed transaction inside context
manager` — 100% dos leads, antes de qualquer scoring.

Contrato pinado aqui, em Postgres real (provas de sessão não funcionam em
mocks):
- `isolated=True` abre sessão dedicada via `session_factory`, entrega à
  operação, commita no sucesso e fecha sempre;
- commit no meio da operação + toque pós-commit em atributo expirado funciona;
- falha reverte o que a operação persistiu e fecha a sessão;
- erro de sessão não é repetível; erro genérico continua repetível.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import sessionmaker

from db_reachable import database_url, is_database_reachable

DB_URL = database_url()
pytestmark = pytest.mark.skipif(
    not is_database_reachable(DB_URL),
    reason="Postgres indisponivel - isolamento de sessao requer banco real",
)


@pytest.fixture()
def pg_isolated():
    from database.models import Organization, OrganizationMember, User

    engine = create_engine(DB_URL)
    closed: list[bool] = []
    base = sessionmaker(bind=engine)

    class RecordingSession(base.class_):
        def close(self):  # noqa: D102
            closed.append(True)
            return super().close()

    fabrica = sessionmaker(bind=engine, class_=RecordingSession)
    db = fabrica()
    suffix = uuid.uuid4().hex[:10]
    org = Organization(name=f"Guard Isolado {suffix}", slug=f"guard-iso-{suffix}")
    user = User(email=f"guard-iso-{suffix}@test.local", password_hash="test", name="Guard Isolado")
    db.add_all([org, user])
    db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id))
    db.commit()
    org_id = org.id
    user_id = user.id
    db.close()
    try:
        yield fabrica, org_id, closed
    finally:
        db = fabrica()
        db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == org_id
        ).delete(synchronize_session=False)
        for model, row_id in ((Organization, org_id), (User, user_id)):
            row = db.query(model).filter(model.id == row_id).first()
            if row:
                db.delete(row)
        db.commit()
        db.close()
        engine.dispose()


def test_isolated_sobrevive_a_commit_no_meio_da_operacao(pg_isolated):
    """Consume-then-touch: commit (cota) + leitura pós-commit funciona."""
    from database.models import Organization
    from services.lead_processing_guard import run_guarded_lead_operation

    fabrica, org_id, closed = pg_isolated

    async def operation(op_db):
        org = op_db.query(Organization).filter(Organization.id == org_id).one()
        op_db.query(Organization).filter(Organization.id == org_id).update(
            {"name": "Guard Isolado Renomeado"}
        )
        op_db.commit()  # como QuotaService.consume faz após Groq 200
        return org.name  # atributo expirado pelo commit: era o InvalidRequestError

    result = asyncio.run(
        run_guarded_lead_operation(
            None, operation, lead_name="L", correlation_id="c",
            isolated=True, session_factory=fabrica,
        )
    )

    assert result.ok is True
    assert result.value == "Guard Isolado Renomeado"
    assert closed, "sessão dedicada deve ser fechada"
    check = fabrica()
    try:
        assert check.query(Organization).filter(Organization.id == org_id).one().name == (
            "Guard Isolado Renomeado"
        )
    finally:
        check.close()


def test_isolated_reverte_falha_e_fecha_sessao(pg_isolated):
    from database.models import Organization
    from services.lead_processing_guard import run_guarded_lead_operation

    fabrica, org_id, closed = pg_isolated

    async def operation(op_db):
        op_db.query(Organization).filter(Organization.id == org_id).update(
            {"name": "Nome Fantasma"}
        )
        op_db.flush()
        raise RuntimeError("scoring falhou")

    result = asyncio.run(
        run_guarded_lead_operation(
            None, operation, lead_name="L", correlation_id="c",
            isolated=True, session_factory=fabrica,
        )
    )

    assert result.ok is False
    assert result.failure is not None
    assert result.failure.error_type == "RuntimeError"
    assert result.failure.retryable is True
    assert closed
    check = fabrica()
    try:
        assert "Fantasma" not in check.query(Organization).filter(
            Organization.id == org_id
        ).one().name
    finally:
        check.close()


def test_isolated_exige_session_factory():
    from services.lead_processing_guard import run_guarded_lead_operation

    async def operation(op_db):
        return "ok"

    with pytest.raises(ValueError, match="session_factory"):
        asyncio.run(
            run_guarded_lead_operation(
                None, operation, lead_name="L", isolated=True,
            )
        )


def test_erro_de_sessao_nao_e_repetivel():
    """InvalidRequestError (sessão) nunca deve voltar à fila como se fosse IA."""
    from contextlib import nullcontext

    from services.lead_processing_guard import run_guarded_lead_operation

    class _FakeDB:
        def begin_nested(self):
            return nullcontext()

        def flush(self):
            pass

    async def explode():
        raise InvalidRequestError("Can't operate on closed transaction")

    result = asyncio.run(run_guarded_lead_operation(_FakeDB(), explode, lead_name="L"))

    assert result.ok is False
    assert result.failure is not None
    assert result.failure.error_type == "InvalidRequestError"
    assert result.failure.retryable is False
