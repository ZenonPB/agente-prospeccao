import os
import sys
import asyncio
import logging
from typing import Optional, Dict

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.database.session import SessionLocal
from src.database.models import Lead, LeadStatus, Enrichment
from src.services.places_service import GooglePlacesService 
from src.services.technical_enrichment_service import TechnicalEnrichmentService 
from src.services.scoring_service import AIScoringService
from src.services.enrichment_orchestrator import process_single_lead
from src.services.domain_utils import normalize_domain

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

async def run_lead_collection(
    query: str,
    max_leads_to_collect: int = 10,
    organization_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
):
    """
    Executa a coleta de leads via Google Places API.

    Usa o mesmo fluxo do `pipeline_worker` da API (dedupe por place_id,
    company_name+website e normalized_domain). `organization_id` é obrigatório
    a partir da Fase A (multi-tenant).
    """
    places_service = GooglePlacesService()
    db = SessionLocal()

    logger.info("Iniciando coleta de leads para: '%s'", query)

    try:
        results = await places_service.search_places(query, max_results=max_leads_to_collect)
        collected_count = 0
        for item in results:
            company_name = item.get("name")
            if not company_name:
                continue

            google_place_id = item.get("place_id_candidate")
            website_url = item.get("website")
            normalized_domain = normalize_domain(website_url)

            existing_lead = db.query(Lead).filter(
                (Lead.organization_id == organization_id) &
                ((Lead.place_id == google_place_id) |
                 ((Lead.company_name == company_name) & (Lead.website == website_url)) |
                 ((Lead.normalized_domain.isnot(None)) & (Lead.normalized_domain == normalized_domain)))
            ).first()

            if existing_lead:
                logger.info("Lead '%s' já existe (ID: %s). Pulando.", company_name, existing_lead.id)
                continue

            new_lead = Lead(
                organization_id=organization_id,
                place_id=google_place_id,
                name=company_name,
                company_name=company_name,
                website=website_url,
                normalized_domain=normalized_domain,
                phone=item.get("phone"),
                email=None,
                category=item.get("category"),
                city=item.get("city"),
                state=item.get("state"),
                country=item.get("country", "Brasil"),
                campaign_id=campaign_id,
                status=LeadStatus.NOVO,
            )
            db.add(new_lead)
            collected_count += 1
            logger.info("Novo lead coletado: %s (Site: %s)", company_name, new_lead.website or 'N/A')

        db.commit()
        logger.info("Coleta de leads finalizada. Total de %d novos leads adicionados ao DB.", collected_count)

    except Exception as e:
        db.rollback()
        logger.error("Erro durante a coleta de leads: %s", e)
        raise
    finally:
        db.close()

async def run_lead_enrichment_and_scoring(limit: int = 5):
    """
    Executa o enriquecimento técnico e o scoring para leads com status NOVO.
    """
    enrichment_service = TechnicalEnrichmentService()
    scoring_service = AIScoringService()
    db = SessionLocal()

    logger.info("Iniciando enriquecimento técnico para %d leads NOVO.", limit)

    try:
        leads_to_enrich = db.query(Lead).filter(
            Lead.status == LeadStatus.NOVO
        ).limit(limit).all()

        if not leads_to_enrich:
            logger.info("Nenhum lead NOVO com website encontrado para enriquecer.")
            return

        for lead in leads_to_enrich:
            logger.info("Processando website para '%s': %s", lead.company_name, lead.website)
            await process_single_lead(lead, enrichment_service, scoring_service, db)

        db.commit()
        logger.info("Enriquecimento técnico finalizado para %d leads.", len(leads_to_enrich))

    except Exception as e:
        db.rollback()
        logger.error("Erro durante o enriquecimento de leads: %s", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(run_lead_enrichment_and_scoring(limit=5))