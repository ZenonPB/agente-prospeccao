import sys
import os

# Add api src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from src.middleware.rate_limit import limiter
from src.routes import leads, campaigns, metrics, pipeline, scoring_templates
from src.routes.auth import router as auth_router

app = FastAPI(
    title="Agente Prospecção API",
    description="API para gestão de prospecção de leads",
    version="0.1.0",
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
app.include_router(leads.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api")
app.include_router(scoring_templates.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Agente Prospecção API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
