import sys
import os

# Add api src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from src.config.settings import settings
from src.middleware.rate_limit import limiter
from src.routes import leads, campaigns, metrics, pipeline, scoring_templates, orgs, analytics, invites, webhooks, tracking, playbooks
from src.routes.auth import router as auth_router

logger = logging.getLogger(__name__)

# Logging central: nível por ambiente, formato simples mas estruturado o
# suficiente para agregação (timestamp + módulo + nível).
logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


async def _cadence_scheduler_loop():
    """Loop periódico: envia follow-ups vencidos (apenas orgs com opt-in).

    Rodado em background no lifespan do app. Usa uma nova sessão por ciclo
    (nenhuma sessão é compartilhada entre tasks — evita race conditions).
    """
    from src.db.session import SessionLocal

    while True:
        try:
            db = SessionLocal()
            try:
                from src.services.cadence_service import run_due
                # SMTP é síncrono — roda fora do event loop.
                sent, deferred = await asyncio.to_thread(run_due, db)
                if sent or deferred:
                    logger.info(
                        "Cadence scheduler: %d enviado(s), %d postergado(s) por throttling",
                        sent, deferred,
                    )
            finally:
                db.close()
        except Exception as e:
            logger.error("Erro no cadence scheduler: %s", e)
        await asyncio.sleep(settings.CADENCE_POLL_SECONDS)


async def _lost_requeue_loop():
    """Loop periódico: re-enfileira leads `PERDIDO` vencidos pela carência
    (business-rules — 90 dias). Poll lento (default 1h); `LOST_REQUEUE_DAYS=0`
    desativa."""
    from src.db.session import SessionLocal

    while True:
        try:
            db = SessionLocal()
            try:
                from src.services.requeue_service import requeue_expired_lost
                requeued = await asyncio.to_thread(
                    lambda: requeue_expired_lost(db, days=settings.LOST_REQUEUE_DAYS),
                )
                if requeued:
                    logger.info(
                        "Lost requeue: %d lead(s) PERDIDO re-enfileirado(s)", requeued
                    )
            finally:
                db.close()
        except Exception as e:
            logger.error("Erro no lost requeue: %s", e)
        await asyncio.sleep(settings.LOST_REQUEUE_POLL_SECONDS)


async def _cadence_close_loop():
    """Loop periódico: marca `PERDIDO`/`NAO_RESPONDEU` cadências cujo
    **envio do encerramento** (dia 14) não teve resposta dentro da carência
    (business-rules). Poll lento (default 1h); `CADENCE_CLOSE_GRACE_DAYS=0`
    desativa."""
    from src.db.session import SessionLocal

    while True:
        try:
            db = SessionLocal()
            try:
                from src.services.cadence_close_service import close_expired_cadences
                closed = await asyncio.to_thread(
                    lambda: close_expired_cadences(
                        db, grace_days=settings.CADENCE_CLOSE_GRACE_DAYS,
                    ),
                )
                if closed:
                    logger.info(
                        "Cadence close: %d lead(s) marcado(s) PERDIDO (encerramento sem resposta)", closed
                    )
            finally:
                db.close()
        except Exception as e:
            logger.error("Erro no cadence close: %s", e)
        await asyncio.sleep(settings.CADENCE_CLOSE_POLL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cadence_scheduler_loop())
    requeue_task = asyncio.create_task(_lost_requeue_loop())
    cadence_close_task = asyncio.create_task(_cadence_close_loop())
    from src.jobs_consumer import job_consumer_loop
    jobs_task = asyncio.create_task(job_consumer_loop())
    logger.info("Cadence scheduler iniciado (poll %ds)", settings.CADENCE_POLL_SECONDS)
    logger.info(
        "Lost requeue iniciado (carência %dd, poll %ds)",
        settings.LOST_REQUEUE_DAYS, settings.LOST_REQUEUE_POLL_SECONDS,
    )
    logger.info(
        "Cadence close iniciado (carência %dd, poll %ds)",
        settings.CADENCE_CLOSE_GRACE_DAYS, settings.CADENCE_CLOSE_POLL_SECONDS,
    )
    logger.info("Job-consumer do pipeline iniciado (poll %ds)", settings.JOB_POLL_SECONDS)
    try:
        yield
    finally:
        task.cancel()
        requeue_task.cancel()
        cadence_close_task.cancel()
        jobs_task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        try:
            await requeue_task
        except asyncio.CancelledError:
            pass
        try:
            await cadence_close_task
        except asyncio.CancelledError:
            pass
        try:
            await jobs_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Agente Prospecção API",
    description="API para gestão de prospecção de leads",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — origins configuráveis via settings.CORS_ORIGINS (deploy: domínio do frontend).
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router, prefix="/api")
app.include_router(invites.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api")
app.include_router(scoring_templates.router, prefix="/api")
app.include_router(orgs.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(playbooks.router, prefix="/api")
# Tracking público (sem auth — o cliente de e-mail acessa): `/t/{token}` e `/c/{token}`.
app.include_router(tracking.router)


@app.get("/")
def root():
    return {"message": "Agente Prospecção API", "docs": "/docs"}


@app.get("/health")
def health():
    """Healthcheck com ping real no banco (para load balancer / orchestrador)."""
    try:
        from sqlalchemy import text
        from src.db.session import SessionLocal
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception:
        logger.exception("Healthcheck falhou ao pingar o banco")
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "error", "database": "unreachable"})
    return {"status": "ok", "database": "ok", "environment": settings.ENVIRONMENT}
