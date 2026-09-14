"""Provas de concorrência do Historical Importer sob Postgres real.

Duas corridas que só o banco resolve — mocks não provam travamento:

- **Confirm concorrente** — n atores com a mesma chave de idempotência e a
  mesma ``expected_version``: o lock pessimista da linha do job somado ao
  versionamento otimista deve permitir exatamente um confirm e responder
  ``VERSION_CONFLICT`` (409) aos demais, deixando o job em QUEUED uma única
  vez (a versão avança exatamente 1) e um único job portando a chave.
- **Claim concorrente** — n consumers chamando ``claim_next_import_job``:
  o ``FOR UPDATE SKIP LOCKED`` garante que um único consumer reivindica o
  job; os demais saem sem trabalho em vez de processarem em duplicidade.

Rodar da raiz:

    python -m pytest tests/test_import_concurrency.py -q
"""
from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db_reachable import database_url, is_database_reachable

DB_URL = database_url()
pytestmark = pytest.mark.skipif(
    not is_database_reachable(DB_URL),
    reason="Postgres indisponivel - provas de concorrencia requerem banco real",
)

N_CONCORRENTES = 5


def _mapping():
    return {"Nome": "name", "Site": "website", "Contato": "contact_name"}


@pytest.fixture(scope="module")
def _engine():
    engine = create_engine(DB_URL)
    yield engine
    engine.dispose()


@pytest.fixture()
def import_db(_engine):
    from database.models import (
        Campaign, Company, CompanyAlias, Contact, ImportAuditEvent, ImportJob,
        ImportRowResult, Lead, Organization, OrganizationMember, Person, User,
    )

    fabrica = sessionmaker(bind=_engine)
    db = fabrica()
    suffix = uuid.uuid4().hex[:10]
    org = Organization(name=f"Import Concorrencia {suffix}", slug=f"import-conc-{suffix}")
    user = User(email=f"import-conc-{suffix}@test.local", password_hash="test", name="Import Concorrencia")
    db.add_all([org, user])
    db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id))
    campaign = Campaign(
        user_id=user.id, organization_id=org.id,
        name="Concorrência E2E", target_city="Araraquara", target_state="SP",
    )
    db.add(campaign)
    db.commit()
    try:
        yield db, org, user, campaign, fabrica
    finally:
        db.rollback()
        job_ids = [item.id for item in db.query(ImportJob).filter(ImportJob.organization_id == org.id).all()]
        if job_ids:
            db.query(ImportAuditEvent).filter(ImportAuditEvent.import_job_id.in_(job_ids)).delete(synchronize_session=False)
            db.query(ImportRowResult).filter(ImportRowResult.import_job_id.in_(job_ids)).delete(synchronize_session=False)
            db.query(ImportJob).filter(ImportJob.id.in_(job_ids)).delete(synchronize_session=False)
        lead_ids = [item.id for item in db.query(Lead).filter(Lead.organization_id == org.id).all()]
        if lead_ids:
            db.query(Contact).filter(Contact.lead_id.in_(lead_ids)).delete(synchronize_session=False)
        db.query(Lead).filter(Lead.organization_id == org.id).delete(synchronize_session=False)
        db.query(Person).filter(Person.organization_id == org.id).delete(synchronize_session=False)
        db.query(CompanyAlias).filter(CompanyAlias.organization_id == org.id).delete(synchronize_session=False)
        db.query(Company).filter(Company.organization_id == org.id).delete(synchronize_session=False)
        db.delete(campaign)
        db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).delete(synchronize_session=False)
        db.delete(org)
        db.delete(user)
        db.commit()
        db.close()


def test_confirm_concorrente_aceita_um_e_rejeita_o_resto_por_versao(import_db):
    db, org, user, campaign, fabrica = import_db
    from src.services.import_job_service import ImportJobError, confirm, create_preview, dry_run
    from database.models import ImportJob

    content = b"Nome,Site,Contato\nEmpresa Concorrente,empresa-concorrente.com.br,Ana\n"
    job = create_preview(db, org.id, user.id, content, "concorrencia.csv", "text/csv", campaign.id)
    preview_version = job.expected_version
    resultado = dry_run(db, org.id, user.id, job.id, _mapping(), preview_version)
    mapping_version = resultado["job"]["mapping_version"]
    version_para_confirmar = resultado["job"]["expected_version"]

    barreira = threading.Barrier(N_CONCORRENTES)
    resultados: list = []

    def tentar_confirm() -> None:
        session = fabrica()
        try:
            barreira.wait(timeout=10)
            confirmado = confirm(
                session, org.id, user.id, job.id, _mapping(),
                mapping_version, version_para_confirmar, "chave-concorrente",
            )
            resultados.append(("ok", confirmado.id))
        except ImportJobError as exc:
            resultados.append((exc.code, None))
        finally:
            session.rollback()
            session.close()

    with ThreadPoolExecutor(max_workers=N_CONCORRENTES) as pool:
        list(pool.map(lambda _: tentar_confirm(), range(N_CONCORRENTES)))

    codigos = [codigo for codigo, _ in resultados]
    sucessos = [job_id for codigo, job_id in resultados if codigo == "ok"]
    conflitos = [codigo for codigo in codigos if codigo == "VERSION_CONFLICT"]

    assert len(sucessos) == 1, f"esperado exatamente 1 confirm aceito, obtido {codigos}"
    assert sucessos[0] == job.id
    assert len(conflitos) == N_CONCORRENTES - 1, (
        f"perdedores deveriam receber VERSION_CONFLICT, obtido {codigos}"
    )

    # Uma única transição para QUEUED: a versão avança exatamente 1 e só um
    # job da organização carrega a chave de idempotência.
    db.expire_all()
    final = db.query(ImportJob).filter(ImportJob.id == job.id).one()
    assert final.status.value == "QUEUED"
    assert final.expected_version == version_para_confirmar + 1
    com_chave = db.query(ImportJob).filter(
        ImportJob.organization_id == org.id,
        ImportJob.idempotency_key == "chave-concorrente",
    ).all()
    assert len(com_chave) == 1 and com_chave[0].id == job.id

    # Replay pós-corrida com a chave e a versão vencedora é idempotente.
    repetido = confirm(
        db, org.id, user.id, job.id, _mapping(),
        mapping_version, final.expected_version, "chave-concorrente",
    )
    assert repetido.id == job.id


def test_claim_concorrente_reivindica_um_unico_consumer(import_db, monkeypatch):
    db, org, user, campaign, fabrica = import_db
    import src.db.session as api_session
    from src.services.import_job_service import (
        claim_next_import_job, confirm, create_preview, dry_run,
    )

    monkeypatch.setattr(api_session, "SessionLocal", fabrica)
    content = b"Nome\nEmpresa Claim\n"
    job = create_preview(db, org.id, user.id, content, "claim.csv", "text/csv", campaign.id)
    resultado = dry_run(db, org.id, user.id, job.id, {"Nome": "name"}, job.expected_version)
    confirm(
        db, org.id, user.id, job.id, {"Nome": "name"},
        resultado["job"]["mapping_version"], resultado["job"]["expected_version"],
        "chave-claim",
    )

    barreira = threading.Barrier(N_CONCORRENTES)
    reivindicas: list = []

    def tentar_claim() -> None:
        session = fabrica()
        try:
            barreira.wait(timeout=10)
            reivindicas.append(claim_next_import_job(session))
        finally:
            session.rollback()
            session.close()

    with ThreadPoolExecutor(max_workers=N_CONCORRENTES) as pool:
        list(pool.map(lambda _: tentar_claim(), range(N_CONCORRENTES)))

    vencedores = [claim for claim in reivindicas if claim is not None]
    assert len(vencedores) == 1, (
        f"SKIP LOCKED deveria entregar o job a um único consumer, obtido {vencedores}"
    )
    assert vencedores[0] == (str(job.id), str(org.id))
