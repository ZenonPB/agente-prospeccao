"""Provas de concorrência do Historical Importer sob Postgres real.

Duas corridas que só o banco resolve — mocks não provam travamento:

- **Confirm concorrente** — n atores com a mesma chave de idempotência e a
  mesma ``expected_version``: o compare-and-swap atômico no PostgreSQL aceita
  exatamente um confirm e responde ``VERSION_CONFLICT`` (409) aos demais,
  deixando o job em QUEUED uma única vez (a versão avança exatamente 1) e um
  único job portando a chave. O escalonamento é controlado por testemunhas:
  todos os requests capturam seu snapshot MVCC antes de qualquer commit e o
  vencedor só efetiva depois disso — perdedor nenhum pode ser reinterpretado
  como replay idempotente.
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
from sqlalchemy import create_engine, event
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


def _staged_confirm_race(fabrica, org, user, job_id, mapping_version, versao_base, chave, n):
    """Corrida de confirms com escalonamento controlado por testemunhas.

    O vencedor roda em background e fica retido pós-flush (CAS aplicado, antes
    do commit) até que os ``n - 1`` perdedores tenham capturado o snapshot de
    abertura e ficado presos no mesmo ``UPDATE``. O commit do vencedor só então
    acontece — depois de todos os snapshots — e nenhum perdedor pode ser
    reinterpretado como retry. Devolve a lista de desfechos.
    """
    from src.services.import_job_service import ImportJobError, confirm

    desfechos: list = []
    cas_aplicado = threading.Event()
    todos_capturaram = threading.Event()
    perdedores = n - 1
    capturou_snapshot = [threading.Event() for _ in range(perdedores)]

    def _marcar_cas_vencedor(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE IMPORT_JOBS"):
            cas_aplicado.set()

    def _reter_vencedor(session, flush_context=None):
        assert todos_capturaram.wait(timeout=20), "perdedores nao capturaram o snapshot"

    def confirmar_vencedor() -> None:
        session = fabrica()
        event.listen(session.connection(), "before_cursor_execute", _marcar_cas_vencedor)
        event.listen(session, "after_flush", _reter_vencedor)
        try:
            confirmado = confirm(
                session, org.id, user.id, job_id, _mapping(),
                mapping_version, versao_base, chave,
            )
            desfechos.append(("ok", confirmado.id))
        except ImportJobError as exc:
            desfechos.append((exc.code, None))
        finally:
            session.rollback()
            session.close()

    executor = ThreadPoolExecutor(max_workers=1)
    futuro = executor.submit(confirmar_vencedor)
    assert cas_aplicado.wait(timeout=20), (
        "o vencedor não chegou ao compare-and-swap"
    )

    def confirmar_perdedor(indice: int) -> None:
        def _sinalizar_snapshot(conn, cursor, statement, parameters, context, executemany):
            if "pg_current_snapshot" in statement:
                capturou_snapshot[indice].set()

        session = fabrica()
        event.listen(session.connection(), "before_cursor_execute", _sinalizar_snapshot)
        try:
            confirmado = confirm(
                session, org.id, user.id, job_id, _mapping(),
                mapping_version, versao_base, chave,
            )
            desfechos.append(("ok", confirmado.id))
        except ImportJobError as exc:
            desfechos.append((exc.code, None))
        finally:
            session.rollback()
            session.close()

    # Perdedores em voo simultâneo: cada um captura o snapshot de abertura e
    # só então trava no mesmo UPDATE retido pelo vencedor.
    with ThreadPoolExecutor(max_workers=perdedores) as pool_perdedores:
        futuros = [pool_perdedores.submit(confirmar_perdedor, i) for i in range(perdedores)]
        try:
            for indice, evt in enumerate(capturou_snapshot):
                assert evt.wait(timeout=20), "perdedor não capturou o snapshot de abertura"
            todos_capturaram.set()
        finally:
            for futuro in futuros:
                futuro.result(timeout=30)
    return desfechos


def test_confirm_concorrente_aceita_um_e_rejeita_o_resto_por_versao(import_db):
    db, org, user, campaign, fabrica = import_db
    from src.services.import_job_service import ImportJobError, confirm, create_preview, dry_run
    from database.models import ImportAuditEvent, ImportJob

    content = b"Nome,Site,Contato\nEmpresa Concorrente,empresa-concorrente.com.br,Ana\n"
    job = create_preview(db, org.id, user.id, content, "concorrencia.csv", "text/csv", campaign.id)
    preview_version = job.expected_version
    resultado = dry_run(db, org.id, user.id, job.id, _mapping(), preview_version)
    mapping_version = resultado["job"]["mapping_version"]
    version_para_confirmar = resultado["job"]["expected_version"]

    desfechos = _staged_confirm_race(
        fabrica, org, user, job.id, mapping_version,
        version_para_confirmar, "chave-concorrente", N_CONCORRENTES,
    )

    codigos = [codigo for codigo, _ in desfechos]
    sucessos = [job_id for codigo, job_id in desfechos if codigo == "ok"]
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

    # Lost-response replay: o retry posterior com o payload original (mesma
    # chave, mesmo mapping, mesma versão-base) é idempotente — sem nova
    # transição, sem nova versão e sem efeitos duplicados.
    versao_antes = final.expected_version
    auditoria_antes = db.query(ImportAuditEvent).filter(
        ImportAuditEvent.import_job_id == job.id,
    ).count()
    repetido = confirm(
        db, org.id, user.id, job.id, _mapping(),
        mapping_version, version_para_confirmar, "chave-concorrente",
    )
    assert repetido.id == job.id
    db.expire_all()
    apos = db.query(ImportJob).filter(ImportJob.id == job.id).one()
    assert apos.status.value == "QUEUED"
    assert apos.expected_version == versao_antes
    auditoria_depois = db.query(ImportAuditEvent).filter(
        ImportAuditEvent.import_job_id == job.id,
    ).count()
    assert auditoria_depois == auditoria_antes


def test_confirm_perdedor_da_corrida_nao_vira_replay_e_retry_posterior_sim(import_db):
    """Separa, sem depender de escalonamento, perdedor da corrida de retry.

    Encenagem determinística: o perdedor captura seu snapshot de abertura e
    fica retido no compare-and-swap enquanto o vencedor ainda não efetivou.
    O vencedor só faz commit depois disso (``after_flush`` espera a testemunha
    do perdedor), então a confirmação nunca esteve visível no snapshot do
    perdedor — ele recebe ``VERSION_CONFLICT``, mesmo carregando a mesma chave
    e a mesma versão-base. Só depois da consolidação um novo request com o
    payload original é reconhecido como replay idempotente.
    """
    db, org, user, campaign, fabrica = import_db
    from src.services.import_job_service import ImportJobError, confirm, create_preview, dry_run
    from database.models import ImportAuditEvent, ImportJob

    content = b"Nome,Site,Contato\nEmpresa Corrida,empresa-corrida.com.br,Bia\n"
    job = create_preview(db, org.id, user.id, content, "corrida.csv", "text/csv", campaign.id)
    resultado = dry_run(db, org.id, user.id, job.id, _mapping(), job.expected_version)
    mapping_version = resultado["job"]["mapping_version"]
    versao_base = resultado["job"]["expected_version"]

    chegou_ao_cas = threading.Event()
    perdedor_ao_cas = threading.Event()
    snapshot_capturado = threading.Event()
    desfecho: list = []

    def _marcar_compare_and_swap(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE IMPORT_JOBS"):
            chegou_ao_cas.set()

    def _marcar_cas_perdedor(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE IMPORT_JOBS"):
            perdedor_ao_cas.set()

    def _marcar_snapshot(conn, cursor, statement, parameters, context, executemany):
        if "pg_current_snapshot" in statement:
            snapshot_capturado.set()

    def confirmar_pelo_perdedor() -> None:
        perdedor = fabrica()
        event.listen(perdedor.connection(), "before_cursor_execute", _marcar_cas_perdedor)
        event.listen(perdedor.connection(), "before_cursor_execute", _marcar_snapshot)
        try:
            confirmado = confirm(
                perdedor, org.id, user.id, job.id, _mapping(),
                mapping_version, versao_base, "chave-corrida",
            )
            desfecho.append(("ok", confirmado.id))
        except ImportJobError as exc:
            desfecho.append((exc.code, None))
        finally:
            perdedor.rollback()
            perdedor.close()

    def confirmar_pelo_vencedor() -> None:
        vencedor = fabrica()
        event.listen(vencedor.connection(), "before_cursor_execute", _marcar_compare_and_swap)
        event.listen(vencedor, "after_flush", _reter_vencedor_ate_testemunha_do_perdedor)
        try:
            confirmado = confirm(
                vencedor, org.id, user.id, job.id, _mapping(),
                mapping_version, versao_base, "chave-corrida",
            )
            desfecho.append(("ok", confirmado.id))
        except ImportJobError as exc:
            desfecho.append((exc.code, None))
        finally:
            vencedor.rollback()
            vencedor.close()

    executor = ThreadPoolExecutor(max_workers=2)

    def _reter_vencedor_ate_testemunha_do_perdedor(session, flush_context=None):
        # O commit do vencedor só sai depois de o perdedor estar preso no CAS:
        # a confirmação nunca esteve visível no snapshot de abertura dele.
        assert perdedor_ao_cas.wait(timeout=20), "o perdedor não chegou ao compare-and-swap"

    # O vencedor entra primeiro: o CAS dele é enviado e trava a linha antes do
    # perdedor existir; o perdedor então captura o snapshot e bloqueia no
    # mesmo UPDATE até o commit do vencedor.
    futuro_vencedor = executor.submit(confirmar_pelo_vencedor)
    assert chegou_ao_cas.wait(timeout=20), "o vencedor não chegou ao compare-and-swap"
    futuro_perdedor = executor.submit(confirmar_pelo_perdedor)
    assert snapshot_capturado.wait(timeout=10), "o perdedor não capturou o snapshot de abertura"
    futuro_vencedor.result(timeout=30)
    futuro_perdedor.result(timeout=30)
    # A ordem de chegada entre as threads não é determinística; o desfecho é.
    vencedores = [job_id for codigo, job_id in desfecho if codigo == "ok"]
    assert vencedores == [job.id], desfecho
    assert [codigo for codigo, _ in desfecho].count("VERSION_CONFLICT") == 1, desfecho
    executor.shutdown(wait=True)

    db.expire_all()
    final = db.query(ImportJob).filter(ImportJob.id == job.id).one()
    assert final.status.value == "QUEUED"
    assert final.expected_version == versao_base + 1
    assert final.confirm_base_version == versao_base
    assert final.confirm_xid, "a confirmação vencedora precisa persistir a testemunha xid"
    assert db.query(ImportAuditEvent).filter(
        ImportAuditEvent.import_job_id == job.id,
        ImportAuditEvent.action == "STATUS_CHANGED",
        ImportAuditEvent.to_status == "QUEUED",
    ).count() == 1

    # Lost-response replay: agora que a confirmação está consolidada, o retry
    # com o payload original (mesma chave/mapping/versão-base) é idempotente.
    versao_consolidada = final.expected_version
    auditoria_antes = db.query(ImportAuditEvent).filter(
        ImportAuditEvent.import_job_id == job.id,
    ).count()
    repetido = confirm(
        db, org.id, user.id, job.id, _mapping(),
        mapping_version, versao_base, "chave-corrida",
    )
    assert repetido.id == job.id
    db.expire_all()
    apos = db.query(ImportJob).filter(ImportJob.id == job.id).one()
    assert apos.status.value == "QUEUED"
    assert apos.expected_version == versao_consolidada
    assert db.query(ImportAuditEvent).filter(
        ImportAuditEvent.import_job_id == job.id,
    ).count() == auditoria_antes


def test_imports_distintos_confirmam_em_paralelo(import_db):
    """Imports diferentes não compartilham lock: os dois confirmam."""
    db, org, user, campaign, fabrica = import_db
    from src.services.import_job_service import confirm, create_preview, dry_run
    from database.models import ImportJob

    preparados = []
    for nome in ("Empresa Paralela A", "Empresa Paralela B"):
        conteudo = f"Nome\n{nome}\n".encode()
        job = create_preview(db, org.id, user.id, conteudo, f"{nome}.csv", "text/csv", campaign.id)
        resultado = dry_run(db, org.id, user.id, job.id, {"Nome": "name"}, job.expected_version)
        preparados.append((job.id, resultado["job"]["mapping_version"], resultado["job"]["expected_version"]))

    barreira = threading.Barrier(len(preparados))
    desfechos: list = []

    def confirmar(registro) -> None:
        job_id, mapping_version, versao_base = registro
        session = fabrica()
        try:
            barreira.wait(timeout=10)
            confirmado = confirm(
                session, org.id, user.id, job_id, {"Nome": "name"},
                mapping_version, versao_base, f"chave-{job_id}",
            )
            desfechos.append(("ok", confirmado.id))
        finally:
            session.rollback()
            session.close()

    with ThreadPoolExecutor(max_workers=len(preparados)) as pool:
        list(pool.map(confirmar, preparados))

    assert sorted(item[0] for item in desfechos) == ["ok", "ok"], desfechos
    db.expire_all()
    for job_id, _mapping_version, versao_base in preparados:
        final = db.query(ImportJob).filter(ImportJob.id == job_id).one()
        assert final.status.value == "QUEUED"
        assert final.expected_version == versao_base + 1


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

    vencedores = [claim for claim in reivindicas if claim is not None and claim[0] == str(job.id)]
    assert len(vencedores) == 1, (
        f"SKIP LOCKED deveria entregar o job a um único consumer, obtido {vencedores}"
    )
    assert vencedores[0] == (str(job.id), str(org.id))
