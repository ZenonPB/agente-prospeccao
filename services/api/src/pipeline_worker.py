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
from src.db.models import Lead, LeadStatus, Campaign, Enrichment, Job, JobStatus, AnalysisProfile

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
    query: str | None = None,
    campaign_id: str | None = None,
    max_leads: int = 10,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Executa o pipeline completo (coleta + enriquecimento + scoring) e gera
    eventos que podem ser enviados para clientes WebSocket.

    Se `campaign_id` for fornecido, a query é construída automaticamente
    a partir dos campos da campanha e o analysis_profile define o
    comportamento do pipeline.
    """
    db = SessionLocal()

    try:
        # Atualiza status do job
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.IN_PROGRESS
            job.started_at = datetime.now(timezone.utc)
            db.commit()

        # --- Resolve campanha e query ---
        campaign = None
        analysis_profile = AnalysisProfile.WEB_PRESENCE

        if campaign_id:
            campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
            if campaign:
                analysis_profile = campaign.analysis_profile or AnalysisProfile.WEB_PRESENCE
                if not query:
                    parts = []
                    if campaign.target_segment:
                        parts.append(campaign.target_segment)
                    if campaign.target_city:
                        parts.append(campaign.target_city)
                    if campaign.target_state:
                        parts.append(campaign.target_state)
                    query = ', '.join(parts) if parts else campaign.name

        if not query:
            query = "empresas"

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
                campaign_id=campaign.id if campaign else None,
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

        # --- Fase 2: Análise por perfil ---
        is_web_presence = analysis_profile == AnalysisProfile.WEB_PRESENCE
        profile_label = "técnica" if is_web_presence else "de negócio"

        yield {"type": "log", "message": f"Iniciando análise {profile_label}...", "timestamp": _ts()}
        yield {"type": "progress", "step": "analise", "percent": 50}

        enrichment_service = TechnicalEnrichmentService()
        scoring_service = AIScoringService()

        leads_to_process = db.query(Lead).filter(
            Lead.status == LeadStatus.NOVO,
        )

        if is_web_presence:
            leads_to_process = leads_to_process.filter(Lead.website.isnot(None))

        if campaign:
            leads_to_process = leads_to_process.filter(Lead.campaign_id == campaign.id)
        else:
            leads_to_process = leads_to_process.filter(Lead.campaign_id == None)

        leads_to_process = leads_to_process.limit(max_leads).all()

        if not leads_to_process:
            yield {"type": "log", "message": "Nenhum lead novo para analisar", "timestamp": _ts()}
        else:
            total_to_process = len(leads_to_process)
            for i, lead in enumerate(leads_to_process):
                yield {
                    "type": "log",
                    "message": f"Analisando: {lead.company_name}",
                    "timestamp": _ts(),
                }

                _, scoring_result = await process_single_lead(
                    lead, enrichment_service, scoring_service, db,
                    analysis_profile=analysis_profile,
                    campaign_target_service=campaign.target_service if campaign else "",
                    campaign_target_segment=campaign.target_segment if campaign else "",
                )

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

                percent = 50 + int((i + 1) / total_to_process * 50)
                yield {"type": "progress", "step": "analise", "percent": min(percent, 100)}

            db.commit()

        # --- Finalizado ---
        lead_filter = Lead.status == LeadStatus.QUALIFICADO
        if campaign:
            lead_filter = lead_filter & (Lead.campaign_id == campaign.id)
        qualified = db.query(Lead).filter(lead_filter).count()

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
