"""
Pipeline worker — adapta a lógica dos workers para publicar eventos
via asyncio para streaming WebSocket em tempo real.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Any

from sqlalchemy.orm import Session

from src.db.session import SessionLocal
from src.db.models import Lead, LeadStatus, Enrichment, Job, JobStatus

# Importa serviços dos workers
import sys
import os
workers_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'workers', 'src')
sys.path.insert(0, workers_path)

from services.places_service import GooglePlacesService
from services.technical_enrichment_service import TechnicalEnrichmentService
from services.scoring_service import AIScoringService
from services.enrichment_orchestrator import process_single_lead

logger = logging.getLogger(__name__)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_pipeline(
    job_id: str,
    query: str,
    max_leads: int = 10,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Executa o pipeline completo (coleta + enriquecimento + scoring) e gera
    eventos que podem ser enviados para clientes WebSocket.
    """
    db = SessionLocal()

    try:
        # Atualiza status do job
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.IN_PROGRESS
            job.started_at = datetime.now(timezone.utc)
            db.commit()

        # --- Fase 1: Coleta ---
        yield {"type": "log", "message": "Conectando ao Google Maps...", "timestamp": _ts()}
        yield {"type": "progress", "step": "coleta", "percent": 0}

        places_service = GooglePlacesService()

        yield {"type": "log", "message": f"Buscando '{query}'...", "timestamp": _ts()}

        results = await places_service.search_places(query, max_results=max_leads)

        logger.info("Pipeline collected %d results", len(results))
        yield {"type": "log", "message": f"{len(results)} estabelecimentos encontrados", "timestamp": _ts()}
        yield {"type": "progress", "step": "coleta", "percent": 30}

        collected_count = 0
        for i, item in enumerate(results):
            company_name = item.get("name")
            if not company_name:
                continue

            google_place_id = item.get("place_id_candidate")
            website_url = item.get("website")

            existing_lead = db.query(Lead).filter(
                (Lead.place_id == google_place_id) |
                ((Lead.company_name == company_name) & (Lead.website == website_url))
            ).first()

            if existing_lead:
                continue

            new_lead = Lead(
                place_id=google_place_id,
                company_name=company_name,
                website=website_url,
                phone=item.get("phone"),
                email=None,
                category=item.get("category"),
                city=item.get("city"),
                state=item.get("state"),
                country=item.get("country", "Brasil"),
                status=LeadStatus.NOVO,
            )
            db.add(new_lead)
            collected_count += 1

            yield {
                "type": "log",
                "message": f"Coletado: {company_name}",
                "timestamp": _ts(),
            }

            percent = 30 + int((i + 1) / len(results) * 20)
            yield {"type": "progress", "step": "coleta", "percent": min(percent, 50)}

        db.commit()
        yield {"type": "log", "message": f"{collected_count} leads novos coletados", "timestamp": _ts()}
        yield {"type": "progress", "step": "coleta", "percent": 50}

        # --- Fase 2: Enriquecimento + Scoring ---
        yield {"type": "log", "message": "Iniciando análise técnica...", "timestamp": _ts()}
        yield {"type": "progress", "step": "enriquecimento", "percent": 50}

        enrichment_service = TechnicalEnrichmentService()
        scoring_service = AIScoringService()

        leads_to_enrich = db.query(Lead).filter(
            Lead.status == LeadStatus.NOVO,
            Lead.website.isnot(None)
        ).limit(max_leads).all()

        if not leads_to_enrich:
            yield {"type": "log", "message": "Nenhum lead novo para analisar", "timestamp": _ts()}
        else:
            total_to_enrich = len(leads_to_enrich)
            for i, lead in enumerate(leads_to_enrich):
                yield {
                    "type": "log",
                    "message": f"Analisando: {lead.company_name}",
                    "timestamp": _ts(),
                }

                _, scoring_result = await process_single_lead(lead, enrichment_service, scoring_service, db)

                score = scoring_result.get("qualification_score", 0) if scoring_result else 0
                status_label = {
                    LeadStatus.QUALIFICADO: "qualificado",
                    LeadStatus.DESQUALIFICADO: "desqualificado",
                }.get(lead.status, "analisado")

                yield {
                    "type": "lead",
                    "name": lead.company_name,
                    "score": score,
                    "status": status_label,
                    "timestamp": _ts(),
                }

                percent = 50 + int((i + 1) / total_to_enrich * 50)
                yield {"type": "progress", "step": "enriquecimento", "percent": min(percent, 100)}

            db.commit()

        # --- Finalizado ---
        qualified = db.query(Lead).filter(
            Lead.campaign_id == None,
            Lead.status == LeadStatus.QUALIFICADO
        ).count()

        yield {
            "type": "done",
            "summary": {
                "collected": collected_count,
                "qualified": qualified,
                "total_processed": len(leads_to_enrich) if leads_to_enrich else 0,
            },
            "timestamp": _ts(),
        }

        # Atualiza job
        if job:
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            db.commit()

    except Exception as e:
        logger.error("Pipeline error: %s", e)
        yield {"type": "error", "message": str(e), "timestamp": _ts()}

        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()

    finally:
        db.close()
