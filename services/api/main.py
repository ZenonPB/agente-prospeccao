import sys
import os

# Add api src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from src.config.settings import settings
from src.middleware.rate_limit import limiter
from src.routes import leads, campaigns, metrics, pipeline, scoring_templates, orgs, analytics, invites, webhooks, tracking, playbooks, notifications, crm, score_feedback
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


async def _deliverability_check_loop():
    """Loop periódico: verifica saúde de entregabilidade de e-mail por org.

    Se bounce_rate > 5% no período recente, pausa `auto_send_email` da org
    e registra alerta no log. Poll lento (default 1h).
    """
    from src.db.session import SessionLocal
    from src.services.analytics_service import AnalyticsService
    from src.db.models import Organization

    while True:
        try:
            db = SessionLocal()
            try:
                orgs = db.query(Organization).filter(
                    Organization.auto_send_email.is_(True)
                ).all()
                for org in orgs:
                    try:
                        analytics = AnalyticsService(db, org.id)
                        result = analytics.check_email_deliverability()
                        if result.get("should_pause"):
                            org.auto_send_email = False
                            db.commit()
                            logger.warning(
                                "Entregabilidade: org %s (%s) — auto_send_email DESATIVADO. "
                                "Bounce rate: %.1f%% (enviados: %d, bounces: %d)",
                                org.id, org.name, result["bounce_rate"],
                                result["sent_in_period"], result["bounced_in_period"]
                            )
                    except Exception as e:
                        logger.error("Erro ao verificar entregabilidade da org %s: %s", org.id, e)
            finally:
                db.close()
        except Exception as e:
            logger.error("Erro no deliverability check: %s", e)
        await asyncio.sleep(settings.DELIVERABILITY_POLL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cadence_scheduler_loop())
    requeue_task = asyncio.create_task(_lost_requeue_loop())
    cadence_close_task = asyncio.create_task(_cadence_close_loop())
    deliverability_task = asyncio.create_task(_deliverability_check_loop())
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
    logger.info(
        "Deliverability check iniciado (poll %ds)", settings.DELIVERABILITY_POLL_SECONDS,
    )
    logger.info("Job-consumer do pipeline iniciado (poll %ds)", settings.JOB_POLL_SECONDS)
    try:
        yield
    finally:
        task.cancel()
        requeue_task.cancel()
        cadence_close_task.cancel()
        deliverability_task.cancel()
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
            await deliverability_task
        except asyncio.CancelledError:
            pass
        try:
            await jobs_task
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
    """Garante que erros inesperados retornam JSON — sem isso, o FastAPI devolve
    HTML 500 e o frontend mostra 'NetworkError' em vez de uma mensagem real."""
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor. Tente novamente."},
    )

# CORS — origins configuráveis via settings.CORS_ORIGINS (deploy: domínio do
# frontend). Aceita lista (pydantic) ou CSV legado, para não quebrar deploys
# antigos que definem a variável como string separada por vírgula.
_cors_raw = settings.CORS_ORIGINS
if isinstance(_cors_raw, str):
    _cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]
else:
    _cors_origins = [str(o).strip() for o in _cors_raw if str(o).strip()]

if _is_prod:
    _bad = [o for o in _cors_origins if "localhost" in o]
    if _bad:
        raise RuntimeError(
            f"CORS_ORIGINS contém localhost em produção: {_bad}. "
            "Defina o domínio real do frontend em CORS_ORIGINS."
        )
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Organization-Id"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injeta headers de segurança em todas as respostas."""

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

# NOTA: HTTPSRedirectMiddleware foi removido. Plataformas como Render/Railway
# já terminam TLS no proxy de borda — o app recebe HTTP internamente. Um
# redirect HTTP→HTTPS no app causa: (1) loop infinito (browser sempre recebe
# HTTP do proxy e o app redireciona para HTTPS que o browser não alcança);
# (2) quebra CORS — o redirect intercepta preflight OPTIONS antes do
# CORSMiddleware, e o Fetch spec não segue redirects em preflights.

# Routers
app.include_router(auth_router, prefix="/api")
# Score-feedback ANTES do router de leads: GET /api/leads/score-feedback não
# pode ser capturado por GET /api/leads/{lead_id}.
app.include_router(score_feedback.router, prefix="/api")
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
app.include_router(notifications.router, prefix="/api")
# CRM Paste — lançamento rápido de leads por texto livre + export xlsx.
app.include_router(crm.router, prefix="/api")
# Tracking público (sem auth — o cliente de e-mail acessa): `/t/{token}` e `/c/{token}`.
app.include_router(tracking.router)


@app.get("/")
def root():
    return {"message": "Prospect.ai API"}


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
    return {"status": "ok", "database": "ok"}
