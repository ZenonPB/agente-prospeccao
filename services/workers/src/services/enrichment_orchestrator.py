"""Orquestrador de enriquecimento + scoring contextual e explicável.

Responsabilidades:
- Carregar template de critérios da campanha (se houver) e/ou fallback 'Genérico'.
- Decidir perfil (web_presence vs business_opportunity) com base no template
  (requires_technical_report) — sobrepõe ao analysis_profile da campanha quando
  o template disser que site é irrelevante.
- Chamar o AIScoringService com facts técnicos + dados cadastrais.
- Persistir todos os campos novos (score_factors, evidence, priority,
  priority_reasoning, executive_summary) estruturados em JSONB/Enum/Text —
  nada de concatenar evidências em string.
"""
import logging
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from database.models import (
    Lead,
    LeadStatus,
    LeadPriority,
    Enrichment,
    AnalysisProfile,
    CampaignScoringTemplate,
)
from services.technical_enrichment_service import TechnicalEnrichmentService
from services.scoring_service import AIScoringService

logger = logging.getLogger(__name__)


def load_scoring_template(
    db: Session,
    explicit_template_id: Optional[str],
    target_service: str,
    target_segment: str = "",
) -> Optional[Dict[str, Any]]:
    """Carrega o template de critérios contextual da campanha.

    Ordem de precedência:
    1. template explicitamente associado à campanha (campaign.scoring_template_id)
    2. match por `service_label` (case-insensitive) em target_service
    3. match por `service_label` em target_segment (fallback comum para campanhas
       onde o usuário preencheu só o segmento, ex.: 'Petshop', 'Academias')
    4. fallback para o template 'Genérico' ativo
    5. None se nada for encontrado (a LLM infere os critérios)

    Sempre retorna a primeira ocorrência com is_active=True.
    """
    if explicit_template_id:
        tmpl = db.query(CampaignScoringTemplate).filter(
            CampaignScoringTemplate.id == explicit_template_id,
            CampaignScoringTemplate.is_active.is_(True),
        ).first()
        if tmpl:
            return _template_to_dict(tmpl)

    if target_service:
        tmpl = db.query(CampaignScoringTemplate).filter(
            sqlfunc.lower(CampaignScoringTemplate.service_label) == target_service.lower().strip(),
            CampaignScoringTemplate.is_active.is_(True),
        ).first()
        if tmpl:
            return _template_to_dict(tmpl)

    if target_segment:
        tmpl = db.query(CampaignScoringTemplate).filter(
            sqlfunc.lower(CampaignScoringTemplate.service_label) == target_segment.lower().strip(),
            CampaignScoringTemplate.is_active.is_(True),
        ).first()
        if tmpl:
            return _template_to_dict(tmpl)

    tmpl = db.query(CampaignScoringTemplate).filter(
        sqlfunc.lower(CampaignScoringTemplate.service_label) == "genérico",
        CampaignScoringTemplate.is_active.is_(True),
    ).first()
    return _template_to_dict(tmpl) if tmpl else None


def _template_to_dict(tmpl: CampaignScoringTemplate) -> Dict[str, Any]:
    return {
        "service_label": tmpl.service_label,
        "positive_signals": tmpl.positive_signals or [],
        "negative_signals": tmpl.negative_signals or [],
        "context_signals": tmpl.context_signals or [],
        "requires_technical_report": bool(tmpl.requires_technical_report),
        "requires_business_data": bool(tmpl.requires_business_data),
        "extra_instructions": tmpl.extra_instructions,
    }


async def process_single_lead(
    lead: Lead,
    enrichment_service: TechnicalEnrichmentService,
    scoring_service: AIScoringService,
    db: Session,
    analysis_profile: AnalysisProfile = AnalysisProfile.WEB_PRESENCE,
    campaign_target_service: str = "",
    campaign_target_segment: str = "",
    scoring_template: Optional[Dict[str, Any]] = None,
    allow_business_fallback: bool = False,
) -> Tuple[Optional[Enrichment], Optional[Dict[str, Any]]]:
    """Processa um lead — enriquecimento + scoring contextual explicável.

    - scoring_template: dict (não ORM) já serializado por load_scoring_template().
      O orchestrator caller é responsável por carregá-lo uma vez por campanha
      e repassar ao batch.
    - allow_business_fallback: quando True, lead sem website em campanha
      WEB_PRESENCE não é desqualificado imediatamente — faz scoring business
      ao invés. Útil para modo reanalyze de leads legados.
    """
    enrichment: Optional[Enrichment] = None
    scoring_data: Optional[Dict[str, Any]] = None

    # Decisão: usar análise técnica? O template pode dizer 'não' mesmo que a
    # campanha esteja marcada como WEB_PRESENCE originalmente.
    use_technical_report = True
    if scoring_template is not None:
        use_technical_report = bool(scoring_template.get("requires_technical_report", True))

    # Lead sem site não pode fazer análise técnica — força path business.
    if not lead.website:
        use_technical_report = False

    if use_technical_report:
        technical_report = await enrichment_service.enrich_website(lead.website)

        enrichment = db.query(Enrichment).filter(Enrichment.lead_id == lead.id).first()
        if enrichment:
            enrichment.raw_technical_data = technical_report
            enrichment.website_exists = technical_report.get("overall_status") != "SITE_OFFLINE"
            enrichment.ssl_ok = technical_report.get("ssl", {}).get("ssl_ok", False)
            enrichment.https_redirect_ok = technical_report.get("ssl", {}).get("https_redirect_ok", False)
            enrichment.cms = technical_report.get("cms_detection")
            enrichment.load_time_ms = technical_report.get("http_headers", {}).get("load_time_ms")
            enrichment.security_issues = technical_report.get("errors", []) + technical_report.get("warnings", [])
        else:
            enrichment = Enrichment(
                lead_id=lead.id,
                raw_technical_data=technical_report,
                website_exists=technical_report.get("overall_status") != "SITE_OFFLINE",
                ssl_ok=technical_report.get("ssl", {}).get("ssl_ok", False),
                https_redirect_ok=technical_report.get("ssl", {}).get("https_redirect_ok", False),
                cms=technical_report.get("cms_detection"),
                load_time_ms=technical_report.get("http_headers", {}).get("load_time_ms"),
                security_issues=technical_report.get("errors", []) + technical_report.get("warnings", []),
            )
            db.add(enrichment)

        scoring_data = await scoring_service.score_lead(
            technical_report,
            target_service=campaign_target_service,
            target_segment=campaign_target_segment,
            template=scoring_template,
            company_name=lead.company_name,
            category=lead.category or "",
            city=lead.city or "",
            state=lead.state or "",
            website=lead.website,
        )
    else:
        # Perfil business_opportunity (ou template alinhou para skipar técnico).
        if not lead.website and analysis_profile == AnalysisProfile.WEB_PRESENCE:
            if allow_business_fallback:
                # Modo reanalise: mantém lead vivo e faz scoring business.
                logger.info(
                    "Lead '%s' sem website (web_presence) — usando fallback business.",
                    lead.company_name,
                )
            else:
                lead.status = LeadStatus.DESQUALIFICADO
                logger.info("Lead '%s' sem website (web_presence). Status: DESQUALIFICADO",
                            lead.company_name)
                return None, None

        scoring_data = await scoring_service.score_business_lead(
            company_name=lead.company_name,
            category=lead.category or "",
            city=lead.city or "",
            state=lead.state or "",
            website=lead.website,
            target_service=campaign_target_service,
            target_segment=campaign_target_segment,
            template=scoring_template,
        )

    _persist_scoring(lead, scoring_data, enrichment)

    if scoring_data:
        logger.info(
            "Lead '%s' score=%s priority=%s status=%s",
            lead.company_name, lead.qualification_score,
            lead.priority.value if lead.priority else "-",
            lead.status.value,
        )
    else:
        lead.status = LeadStatus.ANALISADO
        logger.warning("Falha ao pontuar '%s'. Status mantido ANALISADO.",
                       lead.company_name)

    return enrichment, scoring_data


def _persist_scoring(
    lead: Lead,
    scoring_data: Optional[Dict[str, Any]],
    enrichment: Optional[Enrichment],
) -> None:
    """Aplica scoring_data ao Lead (e enriquece Enrichment com issues_found)."""
    if not scoring_data:
        return

    lead.qualification_score = scoring_data.get("qualification_score", 0)
    lead.qualification_reason = scoring_data.get("qualification_reason") or ""
    lead.primary_need = scoring_data.get("primary_need") or ""

    # Prioridade (chega como string "HOT"/"WARM"/"COLD" ou vazio)
    priority_str = scoring_data.get("priority") or ""
    if priority_str in ("HOT", "WARM", "COLD"):
        lead.priority = LeadPriority[priority_str]
    else:
        lead.priority = None
    lead.priority_reasoning = scoring_data.get("priority_reasoning") or ""

    lead.executive_summary = scoring_data.get("executive_summary") or ""
    lead.pitch_angle = scoring_data.get("pitch_angle") or ""
    lead.suggested_subject = scoring_data.get("suggested_subject") or ""

    # Novos: scoring estruturado — guardado como JSONB puro.
    lead.score_factors = scoring_data.get("score_factors") or []
    lead.evidence = scoring_data.get("evidence") or []

    # Atualiza Enrichment.security_issues com titles das evidências técnicas,
    # preservando o formato histórico (lista de strings) para compatibilidade
    # com componentes que ainda consultam security_issues.
    if enrichment and scoring_data.get("evidence"):
        evidence = scoring_data["evidence"]
        enrichment.security_issues = [
            f"[{e.get('severity','')}] {e.get('title','')}: {e.get('description','')}"
            for e in evidence
        ]

    if lead.qualification_score >= 60:
        lead.status = LeadStatus.QUALIFICADO
    else:
        lead.status = LeadStatus.DESQUALIFICADO
