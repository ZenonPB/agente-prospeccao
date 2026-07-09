import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.db.dependencies import get_db
from src.db.models import Job, JobStatus, JobType, Campaign, User
from src.auth.dependencies import get_current_user
from src.pipeline_worker import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# Active WebSocket connections: job_id -> list of websockets
active_connections: Dict[str, list[WebSocket]] = {}


class StartPipelineRequest(BaseModel):
    query: str
    campaign_id: str | None = None
    max_leads: int = 10


@router.post("/start")
async def start_pipeline(
    request: StartPipelineRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Create a job and start the pipeline in background."""
    # Create job
    job = Job(
        job_type=JobType.LEAD_ENRICHMENT,
        status=JobStatus.PENDING,
        payload={
            "query": request.query,
            "campaign_id": request.campaign_id,
            "max_leads": request.max_leads,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    job_id = str(job.id)

    # Start pipeline task in background
    asyncio.create_task(_run_pipeline_task(job_id, request.query, request.max_leads))

    return {"job_id": job_id, "status": "started"}


async def _run_pipeline_task(job_id: str, query: str, max_leads: int):
    """Background task that runs the pipeline and broadcasts events."""
    try:
        async for event in run_pipeline(job_id=job_id, query=query, max_leads=max_leads):
            # Read connections dynamically (WS may connect after task starts)
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
async def websocket_pipeline(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time pipeline updates."""
    await websocket.accept()

    # Register connection
    if job_id not in active_connections:
        active_connections[job_id] = []
    active_connections[job_id].append(websocket)

    logger.info("WebSocket connected for job %s", job_id)

    try:
        # Keep connection alive and listen for client messages
        while True:
            data = await websocket.receive_text()
            # Client can send ping/pong or commands
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for job %s", job_id)
    finally:
        # Remove connection
        if job_id in active_connections:
            active_connections[job_id] = [
                ws for ws in active_connections[job_id] if ws != websocket
            ]
            if not active_connections[job_id]:
                del active_connections[job_id]
