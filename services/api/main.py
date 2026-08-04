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
from src.routes import leads, campaigns, metrics, pipeline, scoring_templates, orgs, analytics, invites, webhooks
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
                # SMTP é síncrono — roda fora do event loop (item 5.3).
                sent = await asyncio.to_thread(run_due, db)
                if sent:
                    logger.info("Cadence scheduler: %d follow-up(s) enviado(s)", sent)
            finally:
                db.close()
        except Exception as e:
            logger.error("Erro no cadence scheduler: %s", e)
        await asyncio.sleep(settings.CADENCE_POLL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cadence_scheduler_loop())
    logger.info("Cadence scheduler iniciado (poll %ds)", settings.CADENCE_POLL_SECONDS)
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
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
