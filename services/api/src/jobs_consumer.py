"""Job-consumer do pipeline — executa Jobs PENDING em background.

A coleta/enriquecimento de leads roda AQUI (loop dedicado no lifespan da API),
e não dentro do handler da request. Com isso:

- a request só agenda (INSERT em `jobs`) e devolve o `job_id` imediatamente —
  sem `asyncio.create_task` de pipeline preso ao request/event loop;
- os Jobs são consumidos UM POR VEZ (a fila respeita o pacing da Groq e o
  usuário pode sair da tela/recarregar: o job continua e o status fica
  consultável em `GET /api/pipeline/jobs`);
- claim atômico com `FOR UPDATE SKIP LOCKED` — seguro com múltiplos workers;
- Jobs que ficaram presos em IN_PROGRESS (processo morreu no meio) são
  recuperados após `JOB_STALE_MINUTES`;
- cada job executa com o OfferProfileRegistry efetivo da própria organização,
  ligado por ContextVar e isolado de outros jobs/workspaces.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from src.config.settings import settings
from src.db.session import SessionLocal
from src.db.models import Job, JobStatus
from src.services.observability import log_job_event
from src.services.import_job_service import claim_next_import_job, process_import_job

logger = logging.getLogger(__name__)

JOB_STALE_MINUTES = 120

_CLAIM_SQL = text(
    """
    UPDATE jobs
    SET status = :in_progress, started_at = now()
    WHERE id = (
        SELECT id FROM jobs
        WHERE status = :pending
          AND organization_id IS NOT NULL
        ORDER BY created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id, organization_id, campaign_id, payload
    """
)


def _fail_orphan_pipeline_jobs(db) -> None:
    """Falha fechado em jobs legados órfãos sem executar pipeline."""
    orphaned = db.query(Job).filter(
        Job.status == JobStatus.PENDING,
        Job.organization_id.is_(None),
    ).all()
    if not orphaned:
        return
    for job in orphaned:
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = "Job rejeitado: organization_id ausente."
        log_job_event("job_rejected_missing_organization", job_id=str(job.id), campaign_id=str(job.campaign_id) if job.campaign_id else None)
    db.commit()


def _claim_next_job(db) -> Job | None:
    """Pega atomicamente o Job PENDING mais antigo (FOR UPDATE SKIP LOCKED)."""
    row = db.execute(
        _CLAIM_SQL,
        {"in_progress": JobStatus.IN_PROGRESS.name, "pending": JobStatus.PENDING.name},
    ).first()
    if not row:
        return None
    job_id = str(row[0])
    organization_id = row[1]
    db.commit()
    return db.query(Job).filter(
        Job.id == job_id,
        Job.organization_id == organization_id,
    ).first()


def _reclaim_stale_jobs(db) -> None:
    """Marca FAILED jobs IN_PROGRESS abandonados (processo reiniciou no meio)."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=JOB_STALE_MINUTES)
    stale = (
        db.query(Job)
        .filter(
            Job.status == JobStatus.IN_PROGRESS,
            (Job.started_at.is_(None)) | (Job.started_at < cutoff),
        )
        .all()
    )
    for job in stale:
        job.status = JobStatus.FAILED
        job.error_message = "Job interrompido (processo reiniciado) — rode novamente."
        job.completed_at = datetime.now(timezone.utc)
        log_job_event(
            "job_reclaimed",
            job_id=str(job.id),
            organization_id=str(job.organization_id) if job.organization_id else None,
            campaign_id=str(job.campaign_id) if job.campaign_id else None,
            started_at=job.started_at,
            error=job.error_message,
        )
    if stale:
        db.commit()
        logger.warning("Recuperados %d job(s) IN_PROGRESS preso(s).", len(stale))


def _effective_registry_for_job(job: Job):
    """Materializa o registry efetivo antes de entrar no pipeline.

    Usa uma sessão curta e independente: o registry é composto de snapshots
    imutáveis e não mantém objetos ORM vivos. Se a composição falhar, o job
    deve falhar fechado em vez de executar silenciosamente com catálogo global.
    """
    from services.prospecting.effective_offer_registry import build_effective_registry

    if job.organization_id is None:
        raise ValueError("Job de pipeline sem organization_id")
    db = SessionLocal()
    try:
        return build_effective_registry(db, job.organization_id)
    finally:
        db.close()


async def _run_job(job: Job) -> None:
    """Executa o pipeline do job e transmite os eventos para o WebSocket."""
    from src.routes.pipeline import active_connections
    from src.pipeline_worker import run_pipeline
    from services.prospecting.runtime_offer_registry import use_runtime_offer_registry

    payload = job.payload if isinstance(job.payload, dict) else {}
    log_job_event(
        "job_started",
        job_id=str(job.id),
        organization_id=str(job.organization_id) if job.organization_id else None,
        campaign_id=str(job.campaign_id) if job.campaign_id else None,
        started_at=job.started_at,
        job_type=job.job_type.value if job.job_type else None,
    )

    try:
        effective_registry = _effective_registry_for_job(job)
        with use_runtime_offer_registry(effective_registry):
            async for event in run_pipeline(
                job_id=str(job.id),
                query=payload.get("query"),
                campaign_id=payload.get("campaign_id"),
                max_leads=int(payload.get("max_leads", 10)),
                reanalyze_only=bool(payload.get("reanalyze_only", False)),
                unscored_only=bool(payload.get("unscored_only", False)),
                source=payload.get("source") or "places",
                cnae_code=payload.get("cnae_code"),
                cnpjs=payload.get("cnpjs"),
                porte_category=payload.get("porte_category"),
                pncp_start=payload.get("pncp_start"),
                pncp_end=payload.get("pncp_end"),
                pncp_uf=payload.get("pncp_uf"),
                pncp_keyword=payload.get("pncp_keyword"),
            ):
                # Lê conexões dinamicamente (WS pode conectar após o job começar).
                connections = active_connections.get(str(job.id), [])
                dead = []
                for ws in connections:
                    try:
                        await ws.send_json(event)
                    except Exception:  # noqa: BLE001 — um WS morto não derruba o job
                        dead.append(ws)
                for ws in dead:
                    connections.remove(ws)
        final_db = SessionLocal()
        try:
            final_job = final_db.query(Job).filter(
                Job.id == job.id,
                Job.organization_id == job.organization_id,
            ).first()
            if final_job:
                event_name = (
                    "job_completed"
                    if final_job.status == JobStatus.COMPLETED
                    else "job_failed"
                    if final_job.status == JobStatus.FAILED
                    else "job_finished_unknown"
                )
                log_job_event(
                    event_name,
                    job_id=str(final_job.id),
                    organization_id=(
                        str(final_job.organization_id)
                        if final_job.organization_id
                        else None
                    ),
                    campaign_id=(
                        str(final_job.campaign_id) if final_job.campaign_id else None
                    ),
                    started_at=final_job.started_at,
                    error=final_job.error_message,
                    status=final_job.status.value if final_job.status else None,
                )
        finally:
            final_db.close()
    except Exception as e:  # noqa: BLE001 — run_pipeline já trata; defesa extra
        logger.exception("Job %s falhou", job.id)
        log_job_event(
            "job_failed",
            job_id=str(job.id),
            organization_id=str(job.organization_id) if job.organization_id else None,
            campaign_id=str(job.campaign_id) if job.campaign_id else None,
            started_at=job.started_at,
            error=str(e)[:2000],
        )
        db = SessionLocal()
        try:
            row = db.query(Job).filter(
                Job.id == job.id,
                Job.organization_id == job.organization_id,
            ).first()
            if row:
                row.status = JobStatus.FAILED
                row.error_message = str(e)[:2000]
                row.completed_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()


async def _run_import_job(job_id: str, organization_id: str) -> None:
    """Executa o import síncrono de ORM fora do event loop da API."""
    try:
        await asyncio.to_thread(process_import_job, job_id, organization_id)
    except Exception:  # noqa: BLE001 — o serviço persiste o estado de falha
        logger.exception("Import job %s falhou fora do consumer", job_id)


async def job_consumer_loop() -> None:
    """Loop de fundo: consome imports e Jobs PENDING com isolamento tenant-first."""
    while True:
        try:
            db = SessionLocal()
            try:
                _reclaim_stale_jobs(db)
                _fail_orphan_pipeline_jobs(db)
                import_job = claim_next_import_job(db)
                job = None if import_job else _claim_next_job(db)
            finally:
                db.close()
            if import_job is not None:
                logger.info("Job-consumer: executando import %s (org=%s)", import_job[0], import_job[1])
                await _run_import_job(import_job[0], import_job[1])
            elif job is not None:
                logger.info("Job-consumer: executando job %s (%s)", job.id, job.job_type.value)
                await _run_job(job)
        except Exception as e:  # noqa: BLE001 — o loop nunca pode morrer
            logger.error("Erro no job-consumer: %s", e)
        await asyncio.sleep(settings.JOB_POLL_SECONDS)
