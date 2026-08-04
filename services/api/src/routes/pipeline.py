import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, Request, status, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from src.db.dependencies import get_db
from src.db.models import Job, JobStatus, JobType, Campaign, User, Organization
from src.auth.dependencies import get_current_user, get_user_organization
from src.auth.security import decode_access_token
from src.middleware.rate_limit import limiter
from src.pipeline_worker import run_pipeline
from src.services.org_service import user_organization

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# Conexões WebSocket ativas: job_id -> lista de websockets
active_connections: Dict[str, list[WebSocket]] = {}

# Tempo (segundos) para o client enviar a mensagem de autenticação no WS.
WS_AUTH_TIMEOUT_SECONDS = 15


class StartPipelineRequest(BaseModel):
    query: str | None = None
    campaign_id: str | None = None
    max_leads: int = Field(10, ge=1, le=200)
    reanalyze_only: bool = False


@router.post("/start")
@limiter.limit("20/minute")
async def start_pipeline(
    request: Request,
    body: StartPipelineRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Cria um job e inicia o pipeline em background.

    Se `campaign_id` for fornecido, a query é construída automaticamente
    a partir dos campos da campanha (target_segment, target_city, etc.)
    e o analysis_profile da campanha define o comportamento do pipeline.

    Se `reanalyze_only=True`, pula a coleta e reanalisa TODOS os leads da
    campanha usando o scoring contextual novo (útil para leads analizados
    pelo pipeline legado específico de web).

    Rate-limited (item 4.5): 20/min por IP; `max_leads` limitado a 200.
    """
    if not body.query and not body.campaign_id:
        raise HTTPException(
            status_code=422,
            detail="Forneça 'campaign_id' ou 'query' para iniciar o pipeline"
        )

    if body.reanalyze_only and not body.campaign_id:
        raise HTTPException(
            status_code=422,
            detail="Reanálise requer 'campaign_id'"
        )

    campaign = None
    if body.campaign_id:
        campaign = db.query(Campaign).filter(
            Campaign.id == body.campaign_id,
            Campaign.organization_id == _org.id,
        ).first()
        if not campaign:
            raise HTTPException(
                status_code=404,
                detail="Campanha não encontrada",
            )

    job = Job(
        job_type=JobType.LEAD_ENRICHMENT,
        status=JobStatus.PENDING,
        organization_id=_org.id,
        campaign_id=str(campaign.id) if campaign else None,
        payload={
            "query": body.query,
            "campaign_id": body.campaign_id,
            "max_leads": body.max_leads,
            "reanalyze_only": body.reanalyze_only,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    job_id = str(job.id)

    # Inicia pipeline em background
    asyncio.create_task(_run_pipeline_task(
        job_id, body.query, body.campaign_id, body.max_leads,
        body.reanalyze_only,
    ))

    return {"job_id": job_id, "status": "started"}


async def _run_pipeline_task(
    job_id: str, query: str | None, campaign_id: str | None,
    max_leads: int, reanalyze_only: bool = False,
):
    """Executa o pipeline em background e transmite eventos via WebSocket."""
    try:
        async for event in run_pipeline(
            job_id=job_id, query=query, campaign_id=campaign_id,
            max_leads=max_leads, reanalyze_only=reanalyze_only,
        ):
            # Lê conexões dinamicamente (WS pode conectar após a task iniciar)
            connections = active_connections.get(job_id, [])
            dead = []
            for ws in connections:
                try:
                    await ws.send_json(event)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                connections.remove(ws)
    except Exception as e:
        logger.error("Pipeline task error: %s", e)
        connections = active_connections.get(job_id, [])
        error_event = {"type": "error", "message": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}
        for ws in connections:
            try:
                await ws.send_json(error_event)
            except Exception:
                pass


@router.websocket("/ws/{job_id}")
async def websocket_pipeline(
    websocket: WebSocket,
    job_id: str,
):
    """Endpoint WebSocket para atualizações do pipeline em tempo real.

    Autenticação: o client envia `{"type": "auth", "token": "..."}` como
    PRIMEIRA mensagem (o token NÃO vai na query string — evita vazamento em
    logs de proxy). Fecha com 4001 se ausente/inválido; 403 se o job não
    pertencer à organização do usuário.
    """
    await websocket.accept()

    token = None
    try:
        auth_msg = await asyncio.wait_for(
            websocket.receive_text(), timeout=WS_AUTH_TIMEOUT_SECONDS
        )
        try:
            data = json.loads(auth_msg)
        except json.JSONDecodeError:
            await websocket.close(code=4001, reason="Mensagem de autenticação inválida")
            return
        if data.get("type") != "auth" or not data.get("token"):
            await websocket.close(code=4001, reason="Token de autenticação não fornecido")
            return
        token = data["token"]
    except asyncio.TimeoutError:
        await websocket.close(code=4001, reason="Timeout de autenticação")
        return
    except WebSocketDisconnect:
        return

    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Token inválido ou expirado")
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4001, reason="Token malformado")
        return

    db = next(get_db())
    try:
        org = user_organization(db, db.query(User).filter(User.id == user_id).first())
        if org is None:
            await websocket.close(code=403, reason="Usuário sem organização")
            return

        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None or (job.organization_id and str(job.organization_id) != str(org.id)):
            await websocket.close(code=403, reason="Acesso negado a este job")
            return
    finally:
        db.close()

    # Registra conexão
    if job_id not in active_connections:
        active_connections[job_id] = []
    active_connections[job_id].append(websocket)

    logger.info("WebSocket connected for job %s (user: %s)", job_id, payload.get("sub"))

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for job %s", job_id)
    finally:
        # Remove conexão
        if job_id in active_connections:
            active_connections[job_id] = [
                ws for ws in active_connections[job_id] if ws != websocket
            ]
            if not active_connections[job_id]:
                del active_connections[job_id]
