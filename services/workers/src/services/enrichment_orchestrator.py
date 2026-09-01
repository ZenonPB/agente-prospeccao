"""Orquestrador de enriquecimento + scoring contextual e explicável.

Responsabilidades:
- Carregar template de critérios da campanha (feito pelo `template_router`
  chamado no pipeline — exact/fuzzy/LLM/generação; este módulo NÃO resolve
  template, apenas consome o dict já serializado).
- Decidir perfil (web_presence vs business_opportunity) com base no template
  (requires_technical_report) — sobrepõe ao analysis_profile da campanha quando
  o template disser que site é irrelevante.
- Chamar o AIScoringService com facts técnicos + dados cadastrais.
- Persistir todos os campos novos (score_factors, evidence, priority,
  priority_reasoning, executive_summary) estruturados em JSONB/Enum/Text —
  nada de concatenar evidências em string.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from database.models import (
    Lead,
    LeadStatus,
    LeadPriority,
    Enrichment,
    AnalysisProfile,
    Organization,
)
from services.technical_enrichment_service import TechnicalEnrichmentService
from services.scoring_service import AIScoringService
from services import enrichment_ts

logger = logging.getLogger(__name__)

# Fontes de informação de uma empresa que um serviço pode usar para avaliar
# um lead. Declaradas no template (`enrichment_steps`) — o orquestrador roda
# apenas as fontes selecionadas, sem scraping desnecessário.
ENRICHMENT_STEP_KEYS = frozenset({
    "technical_site",   # auditoria do site (CMS, SSL, performance)
    "cnpj_receita",     # dados cadastrais via Receita Federal (porte/CNAE/idade)
    "business_social",  # reputação Google (rating/avaliações) — já coletada no Places
})

DEFAULT_ENRICHMENT_STEPS = ["technical_site", "cnpj_receita", "business_social"]


def resolve_enrichment_steps(
    scoring_template: Optional[Dict[str, Any]],
) -> list:
    """Resolve as fontes de informação que o pipeline deve ativar.

    Template novo (com `enrichment_steps` preenchido) usa a lista declarada.
    Template antigo (só flags binários) faz fallback por compatibilidade:
    `requires_technical_report` → technical_site; `requires_business_data` →
    cnpj_receita. `business_social` é sempre incluída (a reputação Google já
    chega da coleta).
    """
    if scoring_template is None:
        return list(DEFAULT_ENRICHMENT_STEPS)

    declared = scoring_template.get("enrichment_steps")
    if declared:
        return list(dict.fromkeys(s for s in declared if s in ENRICHMENT_STEP_KEYS))

    steps: list = []
    if scoring_template.get("requires_technical_report", True):
        steps.append("technical_site")
    if scoring_template.get("requires_business_data", True):
        steps.append("cnpj_receita")
    steps.append("business_social")
    return list(dict.fromkeys(steps))


async def _enrich_cnpj_facts(
    db: Session,
    lead: Lead,
    want_cnpj: bool,
) -> Tuple[Optional[str], Optional[str]]:
    """Busca dados cadastrais via CNPJ (Receita Federal) e devolve facts.

    Falha do provedor (fora do ar, rate-limit, CNPJ inexistente) NUNCA
    interrompe o batch: loga warning e devolve (None, None) — mesmo padrão do
    `TechnicalEnrichmentService` para site inacessível. Usa TTL de 30 dias
    (`enrichment_ts`), persistindo o DTO em `Enrichment.raw_business_data`.
    """
    if not want_cnpj or not lead or not lead.cnpj:
        return None, None

    fresh = enrichment_ts.is_fresh(enrichment_ts.get_stamp(lead, "cnpj"), "cnpj")
    if not fresh:
        from services.cnpj_service import CnpjService

        try:
            dto = await CnpjService().lookup(lead.cnpj)
        except Exception as e:  # noqa: BLE001 — nunca derruba o batch
            logger.warning(
                "Cadastral: falha ao consultar CNPJ %s do lead %s — seguindo sem.",
                lead.cnpj, lead.company_name,
            )
            logger.debug("Detalhe da falha cadastral: %s", e)
            return None, None
        if not dto:
            logger.warning(
                "Cadastral: CNPJ %s do lead %s não localizado — seguindo sem.",
                lead.cnpj, lead.company_name,
            )
            return None, None

        enrichment = db.query(Enrichment).filter(Enrichment.lead_id == lead.id).first()
        if enrichment is None:
            enrichment = Enrichment(lead_id=lead.id)
            db.add(enrichment)
        enrichment.raw_business_data = dto
        enrichment_ts.stamp(lead, "cnpj")
    else:
        enrichment = db.query(Enrichment).filter(Enrichment.lead_id == lead.id).first()
        if enrichment is None or not enrichment.raw_business_data:
            return None, None
        dto = enrichment.raw_business_data

    company = dto.get("company") or {}
    cnae_info = None
    cnae_code = company.get("cnae_principal")
    cnae_label = company.get("cnae_principal_label")
    if cnae_code or cnae_label:
        cnae_info = f"{cnae_code or ''} - {cnae_label or ''}".lstrip(" -")

    porte = company.get("porte") or company.get("porte_label")
    idade = company.get("idade_anos")
    capital = company.get("capital_social")
    size_parts: list = []
    if porte:
        size_parts.append(f"porte: {porte}")
    if idade is not None:
        size_parts.append(f"idade: {idade} anos")
    if capital is not None:
        size_parts.append(f"capital social: R$ {capital}")
    company_size_info = "; ".join(size_parts) if size_parts else None
    return cnae_info, company_size_info


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
    learned_instructions: Optional[List[str]] = None,
) -> Tuple[Optional[Enrichment], Optional[Dict[str, Any]]]:
    """Processa um lead — enriquecimento + scoring contextual explicável.

    - scoring_template: dict (não ORM) já serializado pelo `template_router`.
      O orchestrator caller é responsável por carregá-lo uma vez por campanha
      e repassar ao batch.
    - allow_business_fallback: mantido para compatibilidade de assinatura —
      hoje o scoring business roda sempre para lead sem site.
    """
    enrichment: Optional[Enrichment] = None
    scoring_data: Optional[Dict[str, Any]] = None

    # Threshold por org: lido uma vez e passado a `_persist_scoring`.
    # Default 60 mantém o comportamento histórico se a org não tiver config.
    qualification_threshold = 60
    if lead.organization_id:
        org = (
            db.query(Organization)
            .filter(Organization.id == lead.organization_id)
            .first()
        )
        if org and org.qualification_threshold is not None:
            qualification_threshold = org.qualification_threshold

    # Decisão: fontes de informação declaradas no template. O template pode
    # dizer 'não quero auditoria de site' mesmo que a campanha esteja marcada
    # como WEB_PRESENCE originalmente (ex.: Engenharia Mecânica).
    steps = resolve_enrichment_steps(scoring_template)
    use_technical_report = "technical_site" in steps

    # Lead sem site não pode fazer análise técnica — força path business.
    if not lead.website:
        use_technical_report = False

    # Dados cadastrais (Receita via CNPJ) quando o template pede — falha do
    # provedor só avisa e segue (nunca derruba o batch).
    cnae_info, company_size_info = await _enrich_cnpj_facts(
        db, lead, want_cnpj="cnpj_receita" in steps,
    )

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

        # Instagram detectado no HTML (passivo) — salva no lead quando ainda
        # não estava preenchido pela coleta.
        social_links = technical_report.get("social_links") or {}
        if not lead.instagram_url and social_links.get("instagram"):
            lead.instagram_url = social_links["instagram"]

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
            google_rating=lead.google_rating,
            google_rating_count=lead.google_rating_count,
            cnae_info=cnae_info,
            company_size_info=company_size_info,
            db=db,
            organization_id=str(lead.organization_id) if lead.organization_id else None,
            learned_instructions=learned_instructions,
        )
    else:
        # Perfil business_opportunity (ou template alinhou para skipar técnico).
        #
        # Lead sem site em campanha WEB_PRESENCE NÃO é
        # desqualificado sem score — para quem vende sites, empresa sem site é
        # público-alvo. Faz scoring business (categoria/cidade/estado + sinais
        # do template). O LLM decide o fito.
        if not lead.website and analysis_profile == AnalysisProfile.WEB_PRESENCE:
            logger.info(
                "Lead '%s' sem website (web_presence) — scoring business.",
                lead.company_name,
            )

        scoring_data = await scoring_service.score_business_lead(
            company_name=lead.company_name,
            category=lead.category or "",
            city=lead.city or "",
            state=lead.state or "",
            website=lead.website,
            target_service=campaign_target_service,
            target_segment=campaign_target_segment,
            template=scoring_template,
            google_rating=lead.google_rating,
            google_rating_count=lead.google_rating_count,
            cnae_info=cnae_info,
            company_size_info=company_size_info,
            db=db,
            organization_id=str(lead.organization_id) if lead.organization_id else None,
            learned_instructions=learned_instructions,
        )

    # Carimba quando cada fonte de análise foi atualizada (site/reviews).
    # O TTL do LinkedIn é carimbado pelo ContactEnrichmentService.
    if use_technical_report and enrichment is not None:
        enrichment_ts.stamp(lead, "site")
    if lead.google_rating is not None or lead.google_rating_count is not None:
        enrichment_ts.stamp(lead, "reviews")

    _persist_scoring(lead, scoring_data, enrichment, qualification_threshold)

    if scoring_data:
        logger.info(
            "Lead '%s' score=%s priority=%s status=%s",
            lead.company_name, lead.qualification_score,
            lead.priority.value if lead.priority else "-",
            lead.status.value,
        )
    else:
        # Falha (ex.: Groq indisponível/rate-limit). Mantém o lead em NOVO para
        # o próximo batch reprocessar — antes isso virava ANALISADO com score 0
        # e o lead ficava preso para sempre (os batches só filtram NOVO).
        lead.status = LeadStatus.NOVO
        logger.warning("Falha ao pontuar '%s'. Status mantido NOVO (será reprocessado).",
                       lead.company_name)

    return enrichment, scoring_data


def _persist_scoring(
    lead: Lead,
    scoring_data: Optional[Dict[str, Any]],
    enrichment: Optional[Enrichment],
    qualification_threshold: int = 60,
) -> None:
    """Aplica scoring_data ao Lead (e enriquece Enrichment com issues_found).

    `qualification_threshold` é o limiar por org para QUALIFICADO/
    DESQUALIFICADO. Default 60 mantém compatibilidade com o comportamento
    histórico. Score == threshold → QUALIFICADO (>=).
    """
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

    if lead.qualification_score >= qualification_threshold:
        lead.status = LeadStatus.QUALIFICADO
    else:
        lead.status = LeadStatus.DESQUALIFICADO
