"""Provas Postgres do lifecycle vertical do Historical Importer.

O teste é pulado sem ``E2E_DATABASE_URL`` e nunca chama provider externo.
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.services.import_job_service import (
    ImportJobError,
    cancel,
    claim_next_import_job,
    confirm,
    create_preview,
    dry_run,
    get_job,
    process_import_job,
)

E2E_DATABASE_URL = os.environ.get("E2E_DATABASE_URL")
pytestmark = pytest.mark.skipif(not E2E_DATABASE_URL, reason="E2E_DATABASE_URL não definido")


@pytest.fixture()
def import_db():
    from database.models import (
        Campaign, Company, CompanyAlias, Contact, ImportAuditEvent, ImportJob,
        ImportRowResult, Lead, Organization, OrganizationMember, Person, User,
    )

    engine = create_engine(E2E_DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    suffix = uuid.uuid4().hex[:10]
    org = Organization(name=f"Import E2E {suffix}", slug=f"import-e2e-{suffix}")
    user = User(email=f"import-{suffix}@test.local", password_hash="test", name="Import E2E")
    db.add_all([org, user])
    db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id))
    campaign = Campaign(user_id=user.id, organization_id=org.id, name="Histórico E2E", target_city="Araraquara", target_state="SP")
    db.add(campaign)
    db.commit()
    try:
        yield db, org, user, campaign
    finally:
        db.rollback()
        job_ids = [item.id for item in db.query(ImportJob).filter(ImportJob.organization_id == org.id).all()]
        if job_ids:
            db.query(ImportAuditEvent).filter(ImportAuditEvent.import_job_id.in_(job_ids)).delete(synchronize_session=False)
            db.query(ImportRowResult).filter(ImportRowResult.import_job_id.in_(job_ids)).delete(synchronize_session=False)
            db.query(ImportJob).filter(ImportJob.id.in_(job_ids)).delete(synchronize_session=False)
        # O processamento cria entidades canônicas que referenciam a org e a
        # campanha; removê-las antes da org evita violação de FK no teardown.
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
        engine.dispose()


def _mapping():
    return {"Nome": "name", "Site": "website", "Contato": "contact_name"}


def test_import_vertical_preview_dry_run_confirm_processa_isolado_e_idempotente(import_db, monkeypatch):
    db, org, user, campaign = import_db
    from sqlalchemy.orm import sessionmaker
    import src.db.session as api_session
    monkeypatch.setattr(api_session, "SessionLocal", sessionmaker(bind=db.get_bind()))
    content = b"Nome,Site,Contato\nEmpresa E2E,empresa-e2e.com.br,Ana\n"
    job = create_preview(db, org.id, user.id, content, "historico.csv", "text/csv", campaign.id)
    preview_version = job.expected_version
    result = dry_run(db, org.id, user.id, job.id, _mapping(), preview_version)
    assert result["report"]["accepted"] == 1
    assert result["job"]["expected_version"] == preview_version + 1

    confirmed = confirm(
        db, org.id, user.id, job.id, _mapping(), result["job"]["mapping_version"],
        result["job"]["expected_version"], "e2e-import-key",
    )
    repeated = confirm(
        db, org.id, user.id, job.id, _mapping(), result["job"]["mapping_version"],
        confirmed.expected_version, "e2e-import-key",
    )
    assert repeated.id == confirmed.id
    with pytest.raises(ImportJobError) as cross_tenant:
        get_job(db, uuid.uuid4(), job.id)
    assert cross_tenant.value.status_code == 404

    claimed = claim_next_import_job(db)
    assert claimed == (str(job.id), str(org.id))
    process_import_job(*claimed)
    # O processamento roda em sessão própria; expirar o mapa de identidade
    # desta sessão evita ler o estado RUNNING anterior ao commit do consumer.
    db.expire_all()
    finished = get_job(db, org.id, job.id)
    assert finished.status.value in {"SUCCEEDED", "PARTIAL"}
    assert finished.accepted_rows == 1

    # Reprocessar o mesmo job não duplica linhas terminais.
    process_import_job(*claimed)
    db.expire_all()
    again = get_job(db, org.id, job.id)
    assert again.accepted_rows == 1


def test_import_cancelamento_antes_do_claim(import_db):
    db, org, user, campaign = import_db
    job = create_preview(db, org.id, user.id, b"Nome\nEmpresa\n", "cancel.csv", "text/csv", campaign.id)
    cancelled = cancel(db, org.id, user.id, job.id, job.expected_version)
    assert cancelled.status.value == "CANCELLED"
    assert claim_next_import_job(db) is None
