"""
Pipeline worker — adapta a lógica dos workers para publicar eventos
via asyncio para streaming WebSocket em tempo real.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from src.db.session import SessionLocal
from src.db.models import Lead, LeadStatus, Campaign, Enrichment, Job, JobStatus, AnalysisProfile, CampaignScoringTemplate

# Importa serviços dos workers
import sys
import os
workers_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'workers', 'src')
sys.path.insert(0, workers_path)

from services.places_service import GooglePlacesService
from services.technical_enrichment_service import TechnicalEnrichmentService
from services.scoring_service import AIScoringService
from services.enrichment_orchestrator import process_single_lead
from services.template_router import route_scoring_template
from services.template_generation_service import TemplateGenerationService
from services.cnae_discovery_service import CnaeDiscoveryService
from services.secret_service import SecretService
from services.domain_utils import normalize_domain

logger = logging.getLogger(__name__)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_pipeline(
    job_id: str,
    query: str | None = None,
    campaign_id: str | None = None,
    max_leads: int = 10,
    reanalyze_only: bool = False,
    source: str = "places",
    cnae_code: str | None = None,
    cnpjs: list[str] | None = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Executa o pipeline completo (coleta + enriquecimento + scoring) e gera
    eventos que podem ser enviados para clientes WebSocket.

    Se `campaign_id` for fornecido, a query é construída automaticamente
    a partir dos campos da campanha e o analysis_profile define o
    comportamento do pipeline.

    Se `reanalyze_only=True`, pula a coleta e reanalisa TODOS os leads da
    campanha (qualquer status anterior) usando o scoring contextual novo.
    Útil para leads que foram analisados pelo pipeline legado específico
    de web antes da migração de scoring contextual.
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
                if not query and not reanalyze_only:
                    if campaign.places_query:
                        # Query sugerida pelo agente — prioridade.
                        query = campaign.places_query
                    else:
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

        # --- Resolução de chaves por organização (BYOK) ---
        # Org com secret próprio usa a própria chave; senão, pool global.
        keys = await SecretService.resolve_all(
            db, str(campaign.organization_id) if campaign else None,
        )
        goog_key = keys.get("GOOGLE_API_KEY")
        groq_key = keys.get("GROQ_API_KEY")

        # --- Coleta (pulada em reanalyze_only) ---
        collected_count = 0
        if reanalyze_only:
            yield {"type": "log", "message": "Modo reanálise: pulando coleta, reusando leads existentes", "timestamp": _ts()}
            yield {"type": "progress", "step": "coleta", "percent": 50}
        elif source == "cnae":
            yield {"type": "log", "message": "Iniciando descoberta de empresas por CNAE e Receita Federal...", "timestamp": _ts()}
            yield {"type": "progress", "step": "coleta", "percent": 10}

            target_state = campaign.target_state if campaign else None
            target_city = campaign.target_city if campaign else None
            cnae_query = cnae_code or (campaign.target_segment if campaign else "CNAE")

            results = await CnaeDiscoveryService.search_by_cnae(
                cnae_code=cnae_query,
                state=target_state,
                city=target_city,
                limit=max_leads,
                cnpjs_input=cnpjs,
            )

            logger.info("Pipeline CNAE discovery collected %d results", len(results))
            yield {"type": "log", "message": f"{len(results)} empresas localizadas via CNAE/Receita", "timestamp": _ts()}
            yield {"type": "progress", "step": "coleta", "percent": 30}

            for item in results:
                company_name = item.get("name")
                cnpj_val = item.get("cnpj")
                place_id_val = item.get("place_id") or f"cnae_{cnpj_val}"
                website_val = item.get("website")
                normalized_domain = normalize_domain(website_val)

                existing_lead = db.query(Lead).filter(
                    (Lead.organization_id == (campaign.organization_id if campaign else None)) &
                    ((Lead.place_id == place_id_val) |
                     (Lead.cnpj == cnpj_val) |
                     ((Lead.normalized_domain.isnot(None)) & (Lead.normalized_domain == normalized_domain)))
                ).first()

                if existing_lead:
                    continue

                new_lead = Lead(
                    organization_id=campaign.organization_id if campaign else None,
                    place_id=place_id_val,
                    name=company_name,
                    company_name=company_name,
                    cnpj=cnpj_val,
                    website=website_val,
                    normalized_domain=normalized_domain,
                    phone=item.get("phone"),
                    address=item.get("address"),
                    category=item.get("cnae_description") or campaign.target_segment,
                    city=item.get("city") or target_city,
                    state=item.get("state") or target_state,
                    status=LeadStatus.NOVO,
                    campaign_id=campaign.id if campaign else None,
                )
                db.add(new_lead)
                collected_count += 1

                db.commit()
                yield {"type": "log", "message": f"{collected_count} novos leads por CNAE salvos", "timestamp": _ts()}
                org_id = campaign.organization_id if campaign else None
                if org_id and collected_count > 0:
                    from src.services.webhook_outbound_service import _dispatch_webhook, build_webhook_payload, build_webhook_headers
                    from src.db.models import Organization as OrgModel
                    org_obj = db.query(OrgModel).filter(OrgModel.id == org_id).first()
                    if org_obj and org_obj.webhook_url:
                        recent = (
                            db.query(Lead)
                            .filter(Lead.organization_id == org_id)
                            .order_by(Lead.created_at.desc())
                            .limit(collected_count)
                            .all()
                        )
                        for fresh in recent:
                            payload = build_webhook_payload(
                                "lead.created",
                                {
                                    "lead_id": str(fresh.id),
                                    "company_name": fresh.company_name,
                                    "city": fresh.city,
                                    "state": fresh.state,
                                    "category": fresh.category,
                                    "campaign_id": str(fresh.campaign_id) if fresh.campaign_id else None,
                                    "created_at": fresh.created_at.isoformat() if fresh.created_at else None,
                                },
                            )
                            headers = build_webhook_headers(org_obj.webhook_secret, "lead.created")
                            asyncio.create_task(
                                _dispatch_webhook(str(org_obj.webhook_url), payload, headers),
                            )
        else:
            yield {"type": "log", "message": "Conectando ao Google Maps...", "timestamp": _ts()}
            yield {"type": "progress", "step": "coleta", "percent": 0}

            places_service = GooglePlacesService(api_key=goog_key)

            # Coleta incremental: place_ids já salvos na organização são
            # excluídos ANTES da paginação, para que cada rodada traga leads
            # realmente novos (e não gaste páginas da API com já coletados).
            org_id = campaign.organization_id if campaign else None
            existing_ids = [
                row[0] for row in db.query(Lead.place_id)
                .filter(Lead.organization_id == org_id)
                .all()
                if row[0]
            ]
            existing_ids_set = set(existing_ids)

            yield {"type": "log", "message": f"Buscando '{query}'...", "timestamp": _ts()}

            results = await places_service.search_places(
                query,
                max_results=max_leads,
                exclude_place_ids=existing_ids_set,
                db=db,
                organization_id=str(campaign.organization_id) if campaign else None,
            )

            logger.info("Pipeline collected %d results", len(results))
            yield {"type": "log", "message": f"{len(results)} estabelecimentos encontrados", "timestamp": _ts()}
            yield {"type": "progress", "step": "coleta", "percent": 30}

            for i, item in enumerate(results):
                company_name = item.get("name")
                if not company_name:
                    continue

                google_place_id = item.get("place_id_candidate")
                website_url = item.get("website")
                normalized_domain = normalize_domain(website_url)

                existing_lead = db.query(Lead).filter(
                    (Lead.organization_id == (campaign.organization_id if campaign else None)) &
                    ((Lead.place_id == google_place_id) |
                     ((Lead.company_name == company_name) & (Lead.website == website_url)) |
                     ((Lead.normalized_domain.isnot(None)) & (Lead.normalized_domain == normalized_domain)))
                ).first()

                if existing_lead:
                    continue

                new_lead = Lead(
                    organization_id=campaign.organization_id if campaign else None,
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
                    # Reputação no Google — sinal de scoring.
                    google_rating=item.get("rating"),
                    google_rating_count=item.get("rating_count"),
                    google_maps_uri=item.get("maps_uri"),
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

        # --- Análise por perfil ---
        is_web_presence = analysis_profile == AnalysisProfile.WEB_PRESENCE
        profile_label = "técnica" if is_web_presence else "de negócio"

        mode_label = " (REAVALIAÇÃO)" if reanalyze_only else ""
        yield {"type": "log", "message": f"Iniciando análise {profile_label}{mode_label}...", "timestamp": _ts()}
        yield {"type": "progress", "step": "analise", "percent": 50}

        enrichment_service = TechnicalEnrichmentService()
        scoring_service = AIScoringService(api_key=groq_key)

        # Carrega template de critérios contextual da campanha (uma vez para todo o batch).
        # Router inteligente: exact → fuzzy → LLM → geração sob demanda → Genérico (itens 1.2/1.3).
        scoring_template = None
        if campaign:
            route_result = await route_scoring_template(
                db,
                target_service=campaign.target_service or "",
                target_segment=campaign.target_segment or "",
                explicit_template_id=str(campaign.scoring_template_id) if campaign.scoring_template_id else None,
                api_key=groq_key,
            )
            scoring_template = route_result.get("template")
            route_label = route_result.get("route")
            matched_label = route_result.get("matched_label")
            if route_label == "GENERATE_NEW":
                yield {
                    "type": "log",
                    "message": "Vertical nova detectada — gerando template de critérios sob demanda...",
                    "timestamp": _ts(),
                }
                try:
                    generation = TemplateGenerationService(api_key=groq_key)
                    scoring_template = await generation.generate(
                        db,
                        target_service=campaign.target_service or "",
                        target_segment=campaign.target_segment or "",
                        organization_id=str(campaign.organization_id),
                    )
                    if scoring_template:
                        # Vincula o template gerado à campanha para reuso.
                        label = scoring_template.get("service_label", "")
                        tmpl_row = (
                            db.query(CampaignScoringTemplate)
                            .filter(
                                sqlfunc.lower(CampaignScoringTemplate.service_label) == label.lower().strip(),
                                CampaignScoringTemplate.is_active.is_(True),
                            )
                            .order_by(CampaignScoringTemplate.created_at.asc())
                            .first()
                        )
                        if tmpl_row:
                            campaign.scoring_template_id = tmpl_row.id
                            db.flush()
                        yield {
                            "type": "log",
                            "message": f"Template gerado: {scoring_template.get('service_label')}",
                            "timestamp": _ts(),
                        }
                except Exception as e:
                    logger.warning("Falha ao gerar template sob demanda: %s", e)
            elif scoring_template:
                yield {
                    "type": "log",
                    "message": f"Template de critérios: {matched_label or scoring_template.get('service_label','(none)')}",
                    "timestamp": _ts(),
                }

        # Seleção dos leads a processar
        leads_query = db.query(Lead)
        if campaign:
            leads_query = leads_query.filter(Lead.organization_id == campaign.organization_id)
        else:
            leads_query = leads_query.filter(Lead.organization_id.is_(None))
        if reanalyze_only:
            if campaign:
                leads_query = leads_query.filter(Lead.campaign_id == campaign.id)
            else:
                leads_query = leads_query.filter(Lead.campaign_id == None)
            # Reanalisa leads da campanha (qualquer status prévio), sobrescrevendo
            # o scoring legado com o contextual novo. Respeita max_leads.
            leads_query = leads_query.limit(max_leads)
            leads_to_process = leads_query.all()
            for lead in leads_to_process:
                lead.status = LeadStatus.NOVO
                lead.qualification_score = 0
                lead.qualification_reason = None
                lead.primary_need = None
                lead.pitch_angle = None
                lead.suggested_subject = None
                lead.priority = None
                lead.priority_reasoning = None
                lead.executive_summary = None
                lead.score_factors = None
                lead.evidence = None
            db.flush()
        else:
            leads_query = leads_query.filter(Lead.status == LeadStatus.NOVO)
            # Em campanhas web, leads SEM site são o público-alvo
            # (compradores de site) — NÃO filtrar por website. O orquestrador roteia
            # lead sem site para o scoring business.
            if campaign:
                leads_query = leads_query.filter(Lead.campaign_id == campaign.id)
            else:
                leads_query = leads_query.filter(Lead.campaign_id == None)
            leads_query = leads_query.limit(max_leads)
            leads_to_process = leads_query.all()

        scored_count = 0
        failed_count = 0
        if not leads_to_process:
            yield {"type": "log", "message": "Nenhum lead novo para analisar", "timestamp": _ts()}
        else:
            total_to_process = len(leads_to_process)
            req_tech = scoring_template.get("requires_technical_report", True) if scoring_template else True
            req_biz = scoring_template.get("requires_business_data", True) if scoring_template else True

            for i, lead in enumerate(leads_to_process):
                yield {
                    "type": "log",
                    "message": f"Analisando: {lead.company_name}",
                    "timestamp": _ts(),
                }

                # Log granular por step de enriquecimento adaptativo
                if not req_tech or not lead.website:
                    reason = "template não exige relatório técnico" if not req_tech else "lead sem website registrado"
                    yield {
                        "type": "log",
                        "message": f"Pulando auditoria técnica de site para {lead.company_name} ({reason}).",
                        "timestamp": _ts(),
                    }
                else:
                    yield {
                        "type": "log",
                        "message": f"Auditando site ({lead.website})...",
                        "timestamp": _ts(),
                    }

                if req_biz and (lead.cnpj or lead.company_name):
                    yield {
                        "type": "log",
                        "message": f"Consultando dados cadastrais/CNAE...",
                        "timestamp": _ts(),
                    }

                _, scoring_result = await process_single_lead(
                    lead, enrichment_service, scoring_service, db,
                    analysis_profile=analysis_profile,
                    campaign_target_service=campaign.target_service if campaign else "",
                    campaign_target_segment=campaign.target_segment if campaign else "",
                    scoring_template=scoring_template,
                    allow_business_fallback=reanalyze_only,
                )

                if scoring_result is None:
                    # Falha na pontuação (ex.: Groq rate-limit apesar do retry).
                    # O orchestrator mantém o lead em NOVO para reprocesso; aqui
                    # só deixamos o feed honesto (nada de "Score: 0" forjado).
                    failed_count += 1
                    yield {
                        "type": "log",
                        "message": (
                            f"{lead.company_name} NÃO foi pontuado (rate-limit/falha do provedor) — "
                            "será reprocessado no próximo batch."
                        ),
                        "timestamp": _ts(),
                    }
                    yield {
                        "type": "lead",
                        "name": lead.company_name,
                        "score": None,
                        "status": "falha",
                        "timestamp": _ts(),
                    }
                else:
                    scored_count += 1
                    score = scoring_result.get("qualification_score", 0)
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

        # --- Enriquecimento automático de decisores (email + LinkedIn) ---
        # Apenas leads QUALIFICADOS (score >= threshold da org) entram na fila
        # de outreach; enriquecer contatos melhora a taxa de contato. Busca
        # passiva. O threshold é aplicado em `enrichment_orchestrator` por org.
        # enriquecer contatos melhora a taxa de contato. Busca passiva.
        if not reanalyze_only:
            yield {
                "type": "log",
                "message": "Enriquecendo decisores dos leads qualificados (e-mail/LinkedIn)...",
                "timestamp": _ts(),
            }

            enrich_query = db.query(Lead).filter(
                Lead.status == LeadStatus.QUALIFICADO
            )
            if campaign:
                enrich_query = enrich_query.filter(Lead.campaign_id == campaign.id)
            else:
                enrich_query = enrich_query.filter(Lead.organization_id.is_(None))
            to_enrich = enrich_query.limit(max_leads).all()

            from services.contact_enrichment_service import ContactEnrichmentService

            enrich_svc = ContactEnrichmentService()
            enriched_count = 0
            for lead in to_enrich:
                try:
                    contacts = await enrich_svc.enrich_contacts(lead, db)
                    if contacts:
                        enriched_count += len(contacts)
                        yield {
                            "type": "log",
                            "message": (
                                f"Decisores de {lead.company_name} enriquecidos "
                                f"({len(contacts)} contato(s))"
                            ),
                            "timestamp": _ts(),
                        }
                except Exception as e:
                    logger.warning("Falha ao enriquecer decisores de %s: %s",
                                   lead.company_name, e)
            db.commit()

            yield {
                "type": "log",
                "message": f"{enriched_count} contatos de decisores enriquecidos",
                "timestamp": _ts(),
            }

        # --- Finalizado ---
        lead_filter = Lead.status == LeadStatus.QUALIFICADO
        if campaign:
            lead_filter = lead_filter & (Lead.campaign_id == campaign.id)
        else:
            lead_filter = lead_filter & (Lead.organization_id.is_(None))
        qualified = db.query(Lead).filter(lead_filter).count()

        yield {
            "type": "done",
            "summary": {
                "collected": collected_count,
                "qualified": qualified,
                "scored": scored_count,
                "failed": failed_count,
                "total_processed": len(leads_to_process) if leads_to_process else 0,
            },
            "timestamp": _ts(),
        }

        # Atualiza job
        if job:
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            if not isinstance(job.payload, dict):
                job.payload = {}
            job.payload["summary"] = {
                "collected": collected_count,
                "qualified": qualified,
                "scored": scored_count,
                "failed": failed_count,
                "total_processed": len(leads_to_process) if leads_to_process else 0,
            }
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
