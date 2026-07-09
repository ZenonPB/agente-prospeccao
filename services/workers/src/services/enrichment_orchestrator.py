import logging
from typing import Dict, Any, Optional, Tuple

from sqlalchemy.orm import Session

from database.models import Lead, LeadStatus, Enrichment, AnalysisProfile
from services.technical_enrichment_service import TechnicalEnrichmentService
from services.scoring_service import AIScoringService

logger = logging.getLogger(__name__)


async def process_single_lead(
    lead: Lead,
    enrichment_service: TechnicalEnrichmentService,
    scoring_service: AIScoringService,
    db: Session,
    analysis_profile: AnalysisProfile = AnalysisProfile.WEB_PRESENCE,
    campaign_target_service: str = "",
    campaign_target_segment: str = "",
) -> Tuple[Optional[Enrichment], Optional[Dict[str, Any]]]:
    """
    Processa um lead de acordo com o perfil de análise da campanha.

    - web_presence: enriquecimento técnico do site + scoring técnico (comportamento atual)
    - business_opportunity: pula enriquecimento técnico, scoring focado em negócio
    """
    enrichment = None
    scoring_data = None

    if analysis_profile == AnalysisProfile.WEB_PRESENCE:
        if not lead.website:
            lead.status = LeadStatus.DESQUALIFICADO
            logger.info("Lead '%s' sem website. Status: DESQUALIFICADO", lead.company_name)
            return None, None

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
                security_issues=technical_report.get('errors', []) + technical_report.get('warnings', []),
            )
            db.add(enrichment)

        scoring_data = await scoring_service.score_lead(
            technical_report,
            target_service=campaign_target_service,
            target_segment=campaign_target_segment,
        )

    else:
        scoring_data = await scoring_service.score_business_lead(
            company_name=lead.company_name,
            category=lead.category or "",
            city=lead.city or "",
            state=lead.state or "",
            website=lead.website,
            target_service=campaign_target_service,
            target_segment=campaign_target_segment,
        )

    if scoring_data:
        lead.qualification_score = scoring_data.get("qualification_score", 0)
        lead.qualification_reason = scoring_data.get("qualification_reason", "")
        lead.primary_need = scoring_data.get("primary_need", "NONE")
        lead.pitch_angle = scoring_data.get("pitch_angle")
        lead.suggested_subject = scoring_data.get("suggested_subject")

        if enrichment and scoring_data.get("issues_found"):
            issues = scoring_data["issues_found"]
            enrichment.security_issues = [
                f"[{i.get('severity','')}] {i.get('title','')}: {i.get('description','')}" for i in issues
            ]

        if lead.qualification_score >= 60:
            lead.status = LeadStatus.QUALIFICADO
        else:
            lead.status = LeadStatus.DESQUALIFICADO
        logger.info("Lead '%s' score: %s -> %s", lead.company_name, lead.qualification_score, lead.status.value)
    else:
        lead.status = LeadStatus.ANALISADO
        logger.warning("Falha ao pontuar '%s'. Status mantido ANALISADO.", lead.company_name)

    return enrichment, scoring_data
