"""
Pipeline worker — adapts the existing worker logic to publish events
via asyncio.Queue for real-time WebSocket streaming.

This module imports the existing services and runs them with event publishing.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Any

from sqlalchemy.orm import Session

from src.db.session import SessionLocal
from src.db.models import Lead, LeadStatus, Enrichment, Job, JobStatus

# Import workers services
import sys
import os
workers_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'workers', 'src')
sys.path.insert(0, workers_path)

from services.places_service import GooglePlacesService
from services.technical_enrichment_service import TechnicalEnrichmentService
from services.scoring_service import AIScoringService

logger = logging.getLogger(__name__)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_pipeline(
    job_id: str,
    query: str,
    max_leads: int = 10,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Runs the full pipeline (collection + enrichment + scoring) and yields
    events that can be forwarded to WebSocket clients.
    """
    db = SessionLocal()

    try:
        # Update job status
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.IN_PROGRESS
            job.started_at = datetime.now(timezone.utc)
            db.commit()

        # --- Phase 1: Collection ---
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

        # --- Phase 2: Enrichment + Scoring ---
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

                # Enrichment
                technical_report = await enrichment_service.enrich_website(lead.website)

                enrichment = db.query(Enrichment).filter(Enrichment.lead_id == lead.id).first()
                if enrichment:
                    enrichment.raw_technical_data = technical_report
                    enrichment.website_exists = technical_report.get('overall_status') != 'SITE_OFFLINE'
                    enrichment.ssl_ok = technical_report.get('ssl', {}).get('ssl_ok', False)
                    enrichment.https_redirect_ok = technical_report.get('ssl', {}).get('https_redirect_ok', False)
                    enrichment.cms = technical_report.get('cms_detection')
                    enrichment.load_time_ms = technical_report.get('http_headers', {}).get('load_time_ms')
                    enrichment.security_issues = technical_report.get('errors', []) + technical_report.get('warnings', [])
                else:
                    enrichment = Enrichment(
                        lead_id=lead.id,
                        raw_technical_data=technical_report,
                        website_exists=technical_report.get('overall_status') != 'SITE_OFFLINE',
                        ssl_ok=technical_report.get('ssl', {}).get('ssl_ok', False),
                        https_redirect_ok=technical_report.get('ssl', {}).get('https_redirect_ok', False),
                        cms=technical_report.get('cms_detection'),
                        load_time_ms=technical_report.get('http_headers', {}).get('load_time_ms'),
                        security_issues=technical_report.get('errors', []) + technical_report.get('warnings', [])
                    )
                    db.add(enrichment)

                # Scoring
                scoring_result = await scoring_service.score_lead(technical_report)
                status_label = "analisado"
                score = 0

                if scoring_result:
                    lead.qualification_score = scoring_result.get("qualification_score", 0)
                    lead.qualification_reason = scoring_result.get("qualification_reason", "")
                    lead.primary_need = scoring_result.get("primary_need", "NONE")
                    score = lead.qualification_score
                    issues = scoring_result.get("issues_found", [])
                    enrichment.security_issues = [
                        f"[{i.get('severity','')}] {i.get('title','')}: {i.get('description','')}" for i in issues
                    ]
                    if lead.qualification_score >= 60:
                        lead.status = LeadStatus.QUALIFICADO
                        status_label = "qualificado"
                    else:
                        lead.status = LeadStatus.DESQUALIFICADO
                        status_label = "desqualificado"
                else:
                    lead.status = LeadStatus.ANALISADO

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

        # --- Done ---
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

        # Update job
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
