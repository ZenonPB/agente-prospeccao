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

    engine = create_engine(E2E_DATABASE_URL, pool_pre_ping=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
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
        yield db, org, user, campaign, Session
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
        engine.dispose()


def _mapping():
    return {"Nome": "name", "Site": "website", "Contato": "contact_name"}


def test_import_vertical_preview_dry_run_confirm_processa_isolado_e_idempotente(import_db, monkeypatch):
    db, org, user, campaign, Session = import_db
    import src.db.session as api_session
    monkeypatch.setattr(api_session, "SessionLocal", Session)
    content = b"Nome,Site,Contato\nEmpresa E2E,empresa-e2e.com.br,Ana\n"
    job = create_preview(db, org.id, user.id, content, "historico.csv", "text/csv", campaign.id)
    preview_version = job.expected_version
    result = dry_run(db, org.id, user.id, job.id, _mapping(), preview_version)
    assert result["report"]["accepted"] == 1
    assert result["job"]["expected_version"] == preview_version + 1

    stale_version = result["job"]["expected_version"]
    confirmed = confirm(
        db, org.id, user.id, job.id, _mapping(), result["job"]["mapping_version"],
        stale_version, "e2e-import-key",
    )
    # Replay com a versão corrente permanece idempotente; retry com a versão
    # antiga observa o conflito em vez de mascará-lo como sucesso.
    repeated = confirm(
        db, org.id, user.id, job.id, _mapping(), result["job"]["mapping_version"],
        confirmed.expected_version, "e2e-import-key",
    )
    assert repeated.id == confirmed.id
    with pytest.raises(ImportJobError) as stale_retry:
        confirm(
            db, org.id, user.id, job.id, _mapping(), result["job"]["mapping_version"],
            stale_version, "e2e-import-key",
        )
    assert stale_retry.value.code == "VERSION_CONFLICT"
    with pytest.raises(ImportJobError) as cross_tenant:
        get_job(db, uuid.uuid4(), job.id)
    assert cross_tenant.value.status_code == 404

    claimed = claim_next_import_job(db)
    assert claimed == (str(job.id), str(org.id))
    process_import_job(*claimed)
    db.expire_all()
    finished = get_job(db, org.id, job.id)
    assert finished.status.value in {"SUCCEEDED", "PARTIAL"}
    assert finished.accepted_rows == 1

    process_import_job(*claimed)
    db.expire_all()
    again = get_job(db, org.id, job.id)
    assert again.accepted_rows == 1


def test_import_preserva_contexto_comercial_historico(import_db, monkeypatch):
    from database.models import ContractOutcome, Lead, LeadStatus, NegotiationStage, PostSaleChannel
    import src.db.session as api_session

    db, org, user, campaign, Session = import_db
    monkeypatch.setattr(api_session, "SessionLocal", Session)
    content = (
        "Nome;Telefone;Status;Responsavel;Prospeccao;Observacoes;Estagio Negociacao;"
        "Contrato Final;Data status;Data Contato Pos Venda;Pos Venda Por;Valor;Previsao Fechamento\n"
        f"Cliente Historico;+5516999999999;RESPONDIDO;{user.email};01/09/2026;Lead vindo da planilha;"
        "ORCAMENTO;EM_ANALISE;05/09/2026;10/09/2026;WHATSAPP;1.234,56;30/09/2026\n"
    ).encode("utf-8")
    job = create_preview(db, org.id, user.id, content, "historico.csv", "text/csv", campaign.id)
    mapping = dict(job.mapping)
    result = dry_run(db, org.id, user.id, job.id, mapping, job.expected_version)
    assert result["report"]["accepted"] == 1
    confirm(
        db, org.id, user.id, job.id, mapping, result["job"]["mapping_version"],
        result["job"]["expected_version"], "historical-commercial-context",
    )
    claimed = claim_next_import_job(db)
    assert claimed == (str(job.id), str(org.id))
    process_import_job(*claimed)
    db.expire_all()

    lead = db.query(Lead).filter(Lead.organization_id == org.id, Lead.company_name == "Cliente Historico").one()
    assert lead.status == LeadStatus.RESPONDIDO
    assert lead.assigned_to_id == user.id
    assert lead.notes == "Lead vindo da planilha"
    assert lead.negotiation_stage == NegotiationStage.ORCAMENTO
    assert lead.contract_outcome == ContractOutcome.EM_ANALISE
    assert lead.post_sale_channel == PostSaleChannel.WHATSAPP
    assert str(lead.value) == "1234.56"
    assert lead.phone == "+5516999999999"
    assert lead.assigned_at is not None
    assert lead.expected_close_date is not None
    assert "status" in (lead.discovery_provenance or {}).get("historical_fields", [])


def test_import_rejeita_owner_de_outro_workspace_e_perdido_sem_motivo(import_db):
    from database.models import Organization, OrganizationMember, User

    db, org, user, campaign, _Session = import_db
    suffix = uuid.uuid4().hex[:8]
    foreign_org = Organization(name=f"Foreign {suffix}", slug=f"foreign-{suffix}")
    foreign_user = User(email=f"foreign-{suffix}@test.local", password_hash="test", name="Foreign")
    db.add_all([foreign_org, foreign_user])
    db.flush()
    db.add(OrganizationMember(organization_id=foreign_org.id, user_id=foreign_user.id))
    db.commit()
    try:
        content = f"Nome,Status,Responsavel\nLead Ruim,PERDIDO,{foreign_user.email}\n".encode()
        job = create_preview(db, org.id, user.id, content, "invalid.csv", "text/csv", campaign.id)
        result = dry_run(db, org.id, user.id, job.id, dict(job.mapping), job.expected_version)
        assert result["report"]["accepted"] == 0
        assert result["report"]["rejected"] == 1
        assert result["report"]["errors"][0]["reason_code"] == "COMMERCIAL_DATA_INVALID"
    finally:
        db.query(OrganizationMember).filter(OrganizationMember.organization_id == foreign_org.id).delete(synchronize_session=False)
        db.delete(foreign_org)
        db.delete(foreign_user)
        db.commit()


def test_import_cancelamento_antes_do_claim(import_db):
    db, org, user, campaign, _Session = import_db
    job = create_preview(db, org.id, user.id, b"Nome\nEmpresa\n", "cancel.csv", "text/csv", campaign.id)
    cancelled = cancel(db, org.id, user.id, job.id, job.expected_version)
    assert cancelled.status.value == "CANCELLED"
    assert claim_next_import_job(db) is None
