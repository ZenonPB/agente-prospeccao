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
from src.middleware.rate_limit import limiter
from src.routes import leads, campaigns, metrics, pipeline, scoring_templates, orgs, analytics, invites
from src.routes.auth import router as auth_router

logger = logging.getLogger(__name__)

# Intervalo do scheduler de cadência (segundos). Item 3.7.2 — envio automático
# de follow-ups vencidos para orgs com `auto_send_email` (opt-in).
CADENCE_POLL_SECONDS = int(os.getenv("CADENCE_POLL_SECONDS", "60"))


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
                sent = run_due(db)
                if sent:
                    logger.info("Cadence scheduler: %d follow-up(s) enviado(s)", sent)
            finally:
                db.close()
        except Exception as e:
            logger.error("Erro no cadence scheduler: %s", e)
        await asyncio.sleep(CADENCE_POLL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cadence_scheduler_loop())
    logger.info("Cadence scheduler iniciado (poll %ds)", CADENCE_POLL_SECONDS)
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

# CORS - allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
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


@app.get("/")
def root():
    return {"message": "Agente Prospecção API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
