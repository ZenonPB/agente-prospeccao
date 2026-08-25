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
  recuperados após `JOB_STALE_MINUTES`.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from src.config.settings import settings
from src.db.session import SessionLocal
from src.db.models import Job, JobStatus

logger = logging.getLogger(__name__)

JOB_STALE_MINUTES = 120

_CLAIM_SQL = text(
    """
    UPDATE jobs
    SET status = :in_progress, started_at = now()
    WHERE id = (
        SELECT id FROM jobs
        WHERE status = :pending
        ORDER BY created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id, campaign_id, payload
    """
)


def _claim_next_job(db) -> Job | None:
    """Pega atomicamente o Job PENDING mais antigo (FOR UPDATE SKIP LOCKED)."""
    row = db.execute(
        _CLAIM_SQL,
        {"in_progress": JobStatus.IN_PROGRESS.name, "pending": JobStatus.PENDING.name},
    ).first()
    if not row:
        return None
    job_id = str(row[0])
    db.commit()
    return db.query(Job).filter(Job.id == job_id).first()


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
    if stale:
        db.commit()
        logger.warning("Recuperados %d job(s) IN_PROGRESS preso(s).", len(stale))


async def _run_job(job: Job) -> None:
    """Executa o pipeline do job e transmite os eventos para o WebSocket."""
    from src.routes.pipeline import active_connections
    from src.pipeline_worker import run_pipeline

    payload = job.payload if isinstance(job.payload, dict) else {}

    try:
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
    except Exception as e:  # noqa: BLE001 — run_pipeline já trata; defesa extra
        logger.error("Job %s falhou: %s", job.id, e)
        db = SessionLocal()
        try:
            row = db.query(Job).filter(Job.id == job.id).first()
            if row:
                row.status = JobStatus.FAILED
                row.error_message = str(e)[:2000]
                row.completed_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()


async def job_consumer_loop() -> None:
    """Loop de fundo: consome Jobs PENDING um por vez (poll JOB_POLL_SECONDS)."""
    while True:
        try:
            db = SessionLocal()
            try:
                _reclaim_stale_jobs(db)
                job = _claim_next_job(db)
            finally:
                db.close()
            if job is not None:
                logger.info("Job-consumer: executando job %s (%s)", job.id, job.job_type.value)
                await _run_job(job)
        except Exception as e:  # noqa: BLE001 — o loop nunca pode morrer
            logger.error("Erro no job-consumer: %s", e)
        await asyncio.sleep(settings.JOB_POLL_SECONDS)
