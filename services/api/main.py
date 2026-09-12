import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from src.config.settings import settings
from src.middleware.rate_limit import limiter
from src.middleware.correlation import CorrelationIdMiddleware
from src.routes import leads, campaigns, metrics, pipeline, scoring_templates, orgs, analytics, invites, webhooks, tracking, playbooks, notifications, crm, score_feedback, intelligence, search, data_intelligence
from src.routes.auth import router as auth_router

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


async def _cadence_scheduler_loop():
    from src.db.session import SessionLocal
    while True:
        try:
            db = SessionLocal()
            try:
                from src.services.cadence_service import run_due
                sent, deferred = await asyncio.to_thread(run_due, db)
                if sent or deferred:
                    logger.info("Cadence scheduler: %d enviado(s), %d postergado(s)", sent, deferred)
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            logger.error("Erro no cadence scheduler: %s", exc)
        await asyncio.sleep(settings.CADENCE_POLL_SECONDS)


async def _lost_requeue_loop():
    from src.db.session import SessionLocal
    while True:
        try:
            db = SessionLocal()
            try:
                from src.services.requeue_service import requeue_expired_lost
                requeued = await asyncio.to_thread(
                    lambda: requeue_expired_lost(db, days=settings.LOST_REQUEUE_DAYS)
                )
                if requeued:
                    logger.info("Lost requeue: %d lead(s) re-enfileirado(s)", requeued)
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            logger.error("Erro no lost requeue: %s", exc)
        await asyncio.sleep(settings.LOST_REQUEUE_POLL_SECONDS)


async def _cadence_close_loop():
    from src.db.session import SessionLocal
    while True:
        try:
            db = SessionLocal()
            try:
                from src.services.cadence_close_service import close_expired_cadences
                closed = await asyncio.to_thread(
                    lambda: close_expired_cadences(db, grace_days=settings.CADENCE_CLOSE_GRACE_DAYS)
                )
                if closed:
                    logger.info("Cadence close: %d lead(s) encerrado(s)", closed)
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            logger.error("Erro no cadence close: %s", exc)
        await asyncio.sleep(settings.CADENCE_CLOSE_POLL_SECONDS)


async def _deliverability_check_loop():
    from src.db.session import SessionLocal
    from src.services.analytics_service import AnalyticsService
    from src.db.models import Organization
    while True:
        try:
            db = SessionLocal()
            try:
                orgs = db.query(Organization).filter(Organization.auto_send_email.is_(True)).all()
                for org in orgs:
                    try:
                        result = AnalyticsService(db, org.id).check_email_deliverability()
                        if result.get("should_pause"):
                            org.auto_send_email = False
                            db.commit()
                            logger.warning(
                                "Entregabilidade: org %s pausada; bounce rate %.1f%%",
                                org.id,
                                result["bounce_rate"],
                            )
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Erro ao verificar entregabilidade da org %s: %s", org.id, exc)
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            logger.error("Erro no deliverability check: %s", exc)
        await asyncio.sleep(settings.DELIVERABILITY_POLL_SECONDS)


async def _event_expiration_loop():
    from src.db.session import SessionLocal
    from services.prospecting.event_opportunity_service import EventOpportunityService
    while True:
        try:
            db = SessionLocal()
            try:
                expired = await asyncio.to_thread(EventOpportunityService().expire_events, db)
                if expired:
                    db.commit()
                    logger.info("Event Discovery: %d evento(s) expirado(s)", expired)
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            logger.error("Erro ao expirar eventos: %s", exc)
        await asyncio.sleep(settings.EVENT_EXPIRATION_POLL_SECONDS)


async def _continuous_intelligence_loop():
    """Revisa workspaces opt-in sem consumir providers por padrão."""
    from src.db.session import SessionLocal
    from src.services.continuous_intelligence_service import ContinuousIntelligenceService

    while True:
        try:
            db = SessionLocal()
            try:
                results = await ContinuousIntelligenceService(db).run_due_organizations()
                executed = [item for item in results if item.get("status") == "success"]
                if executed:
                    logger.info(
                        "Inteligência contínua: %d workspace(s), %d lead(s) alterado(s)",
                        len(executed),
                        sum(int(item.get("changed") or 0) for item in executed),
                    )
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            logger.error("Erro no monitoramento contínuo: %s", exc)
        await asyncio.sleep(settings.CONTINUOUS_INTELLIGENCE_POLL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(_cadence_scheduler_loop()),
        asyncio.create_task(_lost_requeue_loop()),
        asyncio.create_task(_cadence_close_loop()),
        asyncio.create_task(_deliverability_check_loop()),
        asyncio.create_task(_event_expiration_loop()),
        asyncio.create_task(_continuous_intelligence_loop()),
    ]
    from src.jobs_consumer import job_consumer_loop
    tasks.append(asyncio.create_task(job_consumer_loop()))
    logger.info("Cadence scheduler iniciado (poll %ds)", settings.CADENCE_POLL_SECONDS)
    logger.info("Job-consumer iniciado (poll %ds)", settings.JOB_POLL_SECONDS)
    logger.info(
        "Inteligência contínua iniciada (poll %ds; providers exigem opt-in por workspace)",
        settings.CONTINUOUS_INTELLIGENCE_POLL_SECONDS,
    )
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass


_is_prod = settings.ENVIRONMENT == "production"
app = FastAPI(
    title="Prospect.ai API",
    description="Plataforma de inteligência comercial e prospecção B2B",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor. Tente novamente."})


_cors_raw = settings.CORS_ORIGINS
if isinstance(_cors_raw, str):
    _cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
else:
    _cors_origins = [str(o).strip() for o in _cors_raw if str(o).strip()]
if _is_prod:
    _bad = [o for o in _cors_origins if "localhost" in o]
    if _bad:
        raise RuntimeError(f"CORS_ORIGINS contém localhost em produção: {_bad}.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Organization-Id"],
)

if _is_prod:
    from urllib.parse import urlparse
    _trusted_hosts = [
        parsed.netloc
        for parsed in (urlparse(str(o)) for o in _cors_origins)
        if parsed.netloc
    ]
    if _trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=_trusted_hosts)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if _is_prod:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CorrelationIdMiddleware)

app.include_router(auth_router, prefix="/api")
app.include_router(score_feedback.router, prefix="/api")
app.include_router(invites.router, prefix="/api")
app.include_router(leads.router, prefix="/api")
app.include_router(intelligence.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(data_intelligence.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api")
app.include_router(scoring_templates.router, prefix="/api")
app.include_router(orgs.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(webhooks.router, prefix="/api")
app.include_router(playbooks.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(crm.router, prefix="/api")
app.include_router(tracking.router)


@app.get("/")
def root():
    return {"message": "Prospect.ai API"}


@app.get("/health")
def health():
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
    return {"status": "ok", "database": "ok"}
