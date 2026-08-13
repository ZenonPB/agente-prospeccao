import asyncio
import json
import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, Request, status, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from src.db.dependencies import get_db
from src.db.models import Job, JobStatus, JobType, Campaign, User, Organization
from src.auth.dependencies import get_current_user, get_user_organization
from src.auth.security import decode_access_token
from src.middleware.rate_limit import limiter
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
    """Agenda o pipeline na fila de Jobs (background) e retorna o job_id.

    A execução acontece no job-consumer (`jobs_consumer.py`), um job por vez —
    a request só insere o Job e volta imediatamente. O progresso é transmitido
    via WebSocket em `/ws/{job_id}`; o status fica consultável em `GET /jobs`.

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

    return {"job_id": str(job.id), "status": "queued"}


def _serialize_job(job: Job) -> Dict:
    payload = job.payload if isinstance(job.payload, dict) else {}
    return {
        "id": str(job.id),
        "job_type": job.job_type.value if job.job_type else None,
        "status": job.status.value if job.status else None,
        "campaign_id": str(job.campaign_id) if job.campaign_id else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
        "summary": payload.get("summary"),
    }


@router.get("/jobs")
@limiter.limit("60/minute")
async def list_pipeline_jobs(
    request: Request,
    campaign_id: str | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Histórico de jobs do pipeline da organização (para restaurar estado na UI).

    Sem `campaign_id`, lista os jobs mais recentes da organização (default 5).
    O `summary` (collected/scored/qualified/failed) fica no payload do job
    concluído, permitindo recarregar o resumo após navegar/atualizar a página.
    """
    query = db.query(Job).filter(Job.organization_id == _org.id)
    if campaign_id:
        query = query.filter(Job.campaign_id == campaign_id)
    jobs = query.order_by(Job.created_at.desc()).limit(limit).all()
    return {"jobs": [_serialize_job(j) for j in jobs]}       


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
