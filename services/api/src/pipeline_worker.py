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
from sqlalchemy.exc import IntegrityError

from src.db.session import SessionLocal
from src.db.models import Lead, LeadStatus, Campaign, Enrichment, Job, JobStatus, AnalysisProfile, CampaignScoringTemplate, PrescoringDiscard

# Importa serviços dos workers
import sys
import os
workers_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'workers', 'src')
sys.path.insert(0, workers_path)

from services.places_service import GooglePlacesService
from services.technical_enrichment_service import TechnicalEnrichmentService
from services.scoring_service import AIScoringService
from services.enrichment_orchestrator import process_single_lead, resolve_enrichment_steps
from services.template_router import route_scoring_template
from services.template_generation_service import TemplateGenerationService
from services.prospecting_profile_service import resolve_prospecting_profile
from services.discovery_planner_service import DiscoveryPlanner, cnae_discovery_plan
from services.prospecting_hypothesis_service import vertical_pack_for
from services.candidate_pre_scoring_service import CandidatePreScoringService
from services.discovery_multi_query import (
    aggregate_multi_query_results,
    expand_search_queries,
)
from services.cnae_discovery_service import CnaeDiscoveryService
from services.pncp_service import PncpService, default_date_window, format_contract_note
from services.geo_utils import build_location_circle
from services.segment_type_mapping import map_segment_to_places_types
from services.secret_service import SecretService
from services.domain_utils import normalize_domain
from services.company_person_service import CompanyPersonService

logger = logging.getLogger(__name__)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _persist_prescoring_discards(db: Session):
    """Fábrica do callback de auditoria do gate de pre-scoring.

    Upsert idempotente por (campaign_id, place_id): re-coleta atualiza o
    registro em vez de duplicar. Erros são propagados — o chamador decide
    (o serviço de pre-scoring trata auditoria como best-effort).
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    def _persist(records):
        if not records:
            return
        stmt = pg_insert(PrescoringDiscard).values(records)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_prescoring_discards_campaign_place",
            set_={
                "job_id": stmt.excluded.job_id,
                "candidate_data": stmt.excluded.candidate_data,
                "signals": stmt.excluded.signals,
                "discovery_score": stmt.excluded.discovery_score,
                "threshold": stmt.excluded.threshold,
                "reason": stmt.excluded.reason,
                "created_at": sqlfunc.now(),
            },
        )
        db.execute(stmt)
        db.commit()

    return _persist


def _prepare_batch_items(results):
    """Anota cada resultado da coleta com seu `normalized_domain`.

    O domínio é a chave da dedupe por rede (constraint única por org) e precisa
    estar disponível antes de filtrar o lote — sem depender da leitura do banco
    dentro do loop (que, com `autoflush=False`, não vê os leads já adicionados).
    """
    return [
        {**item, "normalized_domain": normalize_domain(item.get("website"))}
        for item in results
    ]


def filter_new_batch_items(items, known_place_ids, known_domains):
    """Remove do lote os resultados que já existem na organização.

    Além de `place_id` já conhecido, pula a SEGUNDA ocorrência do mesmo
    `normalized_domain` dentro do lote: duas lojas da mesma rede com o site
    idêntico (ex.: duas filiais apontando para `site.rede.com.br`) violariam
    `uq_leads_org_normalized_domain` no commit em lote — e com `autoflush=False`
    a query de dedupe dentro do loop não enxerga a irmã recém-adicionada.
    """
    seen_place_ids = set(known_place_ids)
    seen_domains = set(known_domains)
    kept = []
    for item in items:
        place_id = item.get("place_id_candidate")
        domain = item.get("normalized_domain")
        if place_id and place_id in seen_place_ids:
            continue
        if domain and domain in seen_domains:
            continue
        if place_id:
            seen_place_ids.add(place_id)
        if domain:
            seen_domains.add(domain)
        kept.append(item)
    return kept


def _dispatch_lead_created_webhooks(db: Session, org_id: str, lead_ids: list[str]) -> None:
    """Dispara webhook `lead.created` para cada lead recém-criado.

    Usa `asyncio.create_task` porque este pipeline é gerenciado por um
    loop asyncio (jobs consumer / WebSocket). Os tokens de tracking são
    independentes — o disparo é fire-and-forget.
    """
    if not org_id or not lead_ids:
        return
    from src.services.webhook_outbound_service import (
        _dispatch_webhook,
        build_webhook_payload,
        build_webhook_headers,
    )
    from src.db.models import Organization as OrgModel

    org_obj = db.query(OrgModel).filter(OrgModel.id == org_id).first()
    if not org_obj or not org_obj.webhook_url:
        return
    fresh_leads = (
        db.query(Lead)
        .filter(Lead.id.in_(lead_ids), Lead.organization_id == org_id)
        .all()
    )
    for fresh in fresh_leads:
        payload = build_webhook_payload(
            "lead.created",
            {
                "lead_id": str(fresh.id),
                "company_name": fresh.company_name,
                "city": fresh.city,
                "state": fresh.state,
                "category": fresh.category,
                "instagram_url": fresh.instagram_url,
                "campaign_id": str(fresh.campaign_id) if fresh.campaign_id else None,
                "created_at": fresh.created_at.isoformat() if fresh.created_at else None,
            },
        )
        headers = build_webhook_headers(org_obj.webhook_secret, "lead.created")
        asyncio.create_task(
            _dispatch_webhook(str(org_id), str(org_obj.webhook_url), payload, headers),
        )


async def run_pipeline(
    job_id: str,
    query: str | None = None,
    campaign_id: str | None = None,
    max_leads: int = 10,
    reanalyze_only: bool = False,
    unscored_only: bool = False,
    source: str = "places",
    cnae_code: str | None = None,
    cnpjs: list[str] | None = None,
    porte_category: str | None = None,
    pncp_start: str | None = None,
    pncp_end: str | None = None,
    pncp_uf: str | None = None,
    pncp_keyword: str | None = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Executa o pipeline completo (coleta + enriquecimento + scoring) e gera
    eventos que podem ser enviados para clientes WebSocket.

    Se `campaign_id` for fornecido, a query é construída automaticamente
    a partir dos campos da campanha e o analysis_profile define o
    comportamento do pipeline.

    Se `reanalyze_only=True`, pula a coleta e reanalisa OS LEADS da campanha
    (qualquer status anterior) usando o scoring contextual novo. Com
    `unscored_only=True`, restringe aos leads ainda sem pontuação (score NULL
    ou status NOVO) — útil para reprocessar só o que ficou para trás por
    rate-limit/falha, sem re-pontuar o que já pontuou (economiza cota).
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

        # Carrega template de critérios contextual da campanha (uma vez para todo
        # o job, ANTES da coleta — o pre-scoring do discovery precisa do perfil
        # da vertical para o gate de promoção Candidate → Lead).
        # Router inteligente: exact → fuzzy → LLM → geração sob demanda → Genérico (itens 1.2/1.3).
        scoring_template = None

        # Fase 3 (#32 Archetypes): se o template_router não encontrar um
        # template específico, ainda assim detectamos o archetype pelo
        # `target_service`/`target_segment` (landing_pages / industrial_erp /
        # b2b_software) e anotamos o profile_key no job log. Não substitui o
        # template — apenas enriquece o que o template_gen produzir depois.
        if campaign:
            try:
                from services.archetype_service import match_archetype
                arch = match_archetype(
                    target_service=campaign.target_service or "",
                    target_segment=campaign.target_segment or "",
                )
                if arch.get("archetype_id"):
                    yield {
                        "type": "log",
                        "message": (
                            f"Archetype detectado: {arch['archetype_id']} "
                            f"(profile={arch['profile_key']}, conf={arch['confidence']:.2f})"
                        ),
                        "timestamp": _ts(),
                    }
            except Exception as e:  # noqa: BLE001
                logger.debug("Fase3 archetype: %s", e)

        if campaign:
            route_result = await route_scoring_template(
                db,
                target_service=campaign.target_service or "",
                target_segment=campaign.target_segment or "",
                explicit_template_id=str(campaign.scoring_template_id) if campaign.scoring_template_id else None,
                api_key=groq_key,
                organization_id=str(campaign.organization_id) if campaign else None,
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

        # Perfil de prospecção da vertical (docs/melhorias/17): resolvido uma
        # vez por job a partir do template — gate de pre-scoring desligado por
        # padrão (templates sem `prescoring_config` mantêm o fluxo atual).
        prospecting_profile = resolve_prospecting_profile(scoring_template)
        # --- Fase 3: DiscoveryPlanner decide fontes/budget/orçamento pela oferta ---
        # Plano auditável que descreve QUAIS providers rodar e com qual budget.
        # Não toma ações: o pipeline continua chamando providers; o plano apenas
        # declara o que deve ser tentado (docs/melhorias/22 e 23).
        discovery_plan = DiscoveryPlanner().plan(prospecting_profile)
        vertical_pack = vertical_pack_for(prospecting_profile.get("profile_key", "generic"))
        yield {
            "type": "log",
            "message": (
                f"DiscoveryPlanner ({prospecting_profile.get('profile_key','generic')}): "
                f"{len(discovery_plan.get('providers',[]))} providers, "
                f"target_candidates={discovery_plan.get('target_candidates',0)}"
            ),
            "timestamp": _ts(),
        }
        prescoring_discarded = 0
        prescoring_breakdown: Dict[str, int] = {}

        # --- Coleta (pulada em reanalyze_only) ---
        collected_count = 0
        cnae_created_ids: list[str] = []
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
                porte_category=porte_category,
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
                    instagram_url=item.get("instagram_url"),
                    status=LeadStatus.NOVO,
                    campaign_id=campaign.id if campaign else None,
                )
                CompanyPersonService.sync_lead_entities(db, new_lead)
                db.add(new_lead)
                db.commit()
                if new_lead.id is not None:
                    cnae_created_ids.append(str(new_lead.id))
                collected_count += 1

                yield {"type": "log", "message": f"{collected_count} novos leads por CNAE salvos", "timestamp": _ts()}

            org_id = campaign.organization_id if campaign else None
            _dispatch_lead_created_webhooks(db, org_id, cnae_created_ids)
        elif source == "pncp":
            start, end = pncp_start, pncp_end
            if not start or not end:
                start, end = default_date_window(days_back=30)
            uf_label = f" · UF {pncp_uf}" if pncp_uf else ""
            yield {"type": "log", "message": f"Consultando licitações públicas (PNCP): contratos de {start} a {end}{uf_label}...", "timestamp": _ts()}
            yield {"type": "progress", "step": "coleta", "percent": 10}

            suppliers = await PncpService.search_supplier_contracts(
                start,
                end,
                uf=pncp_uf,
                keyword=pncp_keyword,
                max_suppliers=max_leads,
            )

            logger.info("Pipeline PNCP coletou %d fornecedores", len(suppliers))
            yield {"type": "log", "message": f"{len(suppliers)} fornecedores vencedores localizados no PNCP", "timestamp": _ts()}
            yield {"type": "progress", "step": "coleta", "percent": 30}

            org_id = campaign.organization_id if campaign else None
            existing_ids = {
                row[0]
                for row in db.query(Lead.place_id).filter(Lead.organization_id == org_id).all()
                if row[0]
            }
            existing_domains = {
                row[0]
                for row in db.query(Lead.normalized_domain)
                .filter(Lead.organization_id == org_id, Lead.normalized_domain.isnot(None))
                .all()
                if row[0]
            }
            existing_cnpjs = {
                row[0]
                for row in db.query(Lead.cnpj).filter(Lead.organization_id == org_id).all()
                if row[0]
            }

            pncp_created_ids: list[str] = []
            for supplier in suppliers:
                details = (await PncpService.enrich_supplier(supplier)).get("details") or {}
                company_name = details.get("name") or supplier.get("supplier_name")
                cnpj_val = supplier.get("cnpj")
                place_id_val = supplier.get("place_id_candidate") or f"pncp_{cnpj_val}"
                website_val = details.get("website")
                normalized_domain = normalize_domain(website_val)

                if place_id_val in existing_ids or cnpj_val in existing_cnpjs:
                    continue
                if normalized_domain and normalized_domain in existing_domains:
                    continue

                target_state = campaign.target_state if campaign else None
                target_city = campaign.target_city if campaign else None
                new_lead = Lead(
                    organization_id=org_id,
                    place_id=place_id_val,
                    name=details.get("name"),
                    company_name=company_name or f"CNPJ {cnpj_val}",
                    cnpj=cnpj_val,
                    website=website_val,
                    normalized_domain=normalized_domain,
                    phone=details.get("phone"),
                    address=details.get("address"),
                    category=details.get("cnae_description")
                    or (campaign.target_segment if campaign else None),
                    city=details.get("city") or target_city or "",
                    state=details.get("state") or target_state,
                    status=LeadStatus.NOVO,
                    campaign_id=campaign.id if campaign else None,
                    notes=format_contract_note(supplier),
                )
                try:
                    with db.begin_nested():
                        CompanyPersonService.sync_lead_entities(db, new_lead)
                        db.add(new_lead)
                        db.flush()
                except IntegrityError as exc:
                    logger.warning("Lead duplicado ignorado na coleta PNCP: %s", exc.orig or exc)
                    continue

                if new_lead.id is not None:
                    pncp_created_ids.append(str(new_lead.id))
                    existing_ids.add(place_id_val)
                    if cnpj_val:
                        existing_cnpjs.add(cnpj_val)
                    if normalized_domain:
                        existing_domains.add(normalized_domain)
                collected_count += 1

                yield {"type": "log", "message": f"Coletado (licitante): {new_lead.company_name}", "timestamp": _ts()}

            db.commit()
            _dispatch_lead_created_webhooks(db, org_id, [lid for lid in pncp_created_ids if lid])
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
            # Domínios já cadastrados da org — impedem a 2ª loja da mesma rede
            # (mesmo `normalized_domain`) dentro do lote, que violaria
            # `uq_leads_org_normalized_domain` no commit em lote.
            existing_domains = {
                row[0]
                for row in db.query(Lead.normalized_domain)
                .filter(Lead.organization_id == org_id, Lead.normalized_domain.isnot(None))
                .all()
                if row[0]
            }

            yield {"type": "log", "message": f"Buscando '{query}'...", "timestamp": _ts()}
            places_created_ids: list[str] = []

            # Filtros geográficos e de tipo para a Places API (defesas em
            # profundidade contra resultados irrelevantes):
            # - locationRestriction.circle: restringe a busca ao raio da cidade
            #   (resolve a causa raiz — a API não devolve lixo de fora).
            # - includedType: filtra por categoria primária (physiotherapist,
            #   restaurant, etc.) — evita empresas que mencionam o termo em
            #   texto mas não pertencem ao segmento.
            # - filter_city/filter_state: pós-filtro case/accents-insensitive
            #   (última defesa — se a API ainda devolver algo fora do raio).
            target_city = campaign.target_city if campaign else None
            target_state = campaign.target_state if campaign else None
            target_segment = campaign.target_segment if campaign else None
            location_bias = build_location_circle(
                target_city, target_state,
                api_key=goog_key,
            )
            included_type = map_segment_to_places_types(target_segment)

            if location_bias:
                logger.info("Location bias: city=%s, state=%s → circle at %s",
                            target_city, target_state,
                            location_bias["circle"]["center"])
            if included_type:
                logger.info("Included type: %s (segment=%s)", included_type, target_segment)

            # Multi-query (docs/melhorias/04): executa TODAS as consultas
            # declaradas na campanha (variedade semântica, limite por query
            # proporcional — nunca paginação cega) e agrega dedup por
            # place_id com `source_queries` auditáveis.
            search_queries = expand_search_queries(campaign, fallback_query=query)
            per_query_limit = max(1, -(-max_leads // len(search_queries)))
            per_query_results = []
            for sq in search_queries:
                found = await places_service.search_places(
                    sq,
                    max_results=per_query_limit,
                    exclude_place_ids=existing_ids_set,
                    db=db,
                    organization_id=str(campaign.organization_id) if campaign else None,
                    filter_city=target_city,
                    filter_state=target_state,
                    location_bias=location_bias,
                    included_type=included_type,
                )
                per_query_results.append((sq, found))
                logger.info("Places multi-query %r: %d resultados", sq, len(found))
            results = aggregate_multi_query_results(per_query_results)

            batch_items = filter_new_batch_items(
                _prepare_batch_items(results), existing_ids_set, existing_domains,
            )

            # Gate de promoção Candidate → Lead (docs/melhorias/01/06/07):
            # pré-ranking determinístico e barato. Candidatos abaixo do
            # threshold NÃO viram Lead e NÃO consomem enriquecimento caro.
            # Desligado quando o template não declara `prescoring_config`.
            if batch_items and prospecting_profile["prescoring"]["enabled"]:
                prescoring_context = {
                    "organization_id": str(campaign.organization_id) if campaign else None,
                    "campaign_id": str(campaign.id) if campaign else None,
                    "job_id": str(job.id) if job else None,
                }
                batch_items, prescoring_stats = CandidatePreScoringService().select_candidates(
                    batch_items, prospecting_profile,
                    persist_fn=_persist_prescoring_discards(db),
                    context=prescoring_context,
                )
                prescoring_discarded = prescoring_stats["discarded"]
                prescoring_breakdown = {
                    "below_threshold": prescoring_stats["below_threshold"],
                    "top_k_cut": prescoring_stats["top_k_cut"],
                }
                yield {
                    "type": "log",
                    "message": (
                        f"Pré-scoring ({prospecting_profile['profile_key']}): "
                        f"{prescoring_stats['eligible']}/{prescoring_stats['evaluated']} candidatos aprovados "
                        f"(threshold={prospecting_profile['prescoring']['threshold']}, "
                        f"{prescoring_stats['below_threshold']} abaixo do threshold, "
                        f"{prescoring_stats['top_k_cut']} cortados por top_k)"
                    ),
                    "timestamp": _ts(),
                }

            logger.info("Pipeline collected %d results", len(results))
            yield {"type": "log", "message": f"{len(results)} estabelecimentos encontrados ({len(batch_items)} novos)", "timestamp": _ts()}
            yield {"type": "progress", "step": "coleta", "percent": 30}

            for i, item in enumerate(batch_items):
                company_name = item.get("name")
                if not company_name:
                    continue

                google_place_id = item.get("place_id_candidate")
                website_url = item.get("website")
                normalized_domain = item.get("normalized_domain")

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
                    instagram_url=item.get("instagram_url"),
                    campaign_id=campaign.id if campaign else None,
                    status=LeadStatus.NOVO,
                )
                # SAVEPOINT por lead: o flush expõe o lead às dedupes seguintes
                # e, se alguma linha colidir (ex.: corrida entre jobs), só ela
                # é descartada — o lote inteiro não rola para trás.
                try:
                    with db.begin_nested():
                        CompanyPersonService.sync_lead_entities(db, new_lead)
                        db.add(new_lead)
                        db.flush()
                except IntegrityError as exc:
                    logger.warning(
                        "Lead duplicado ignorado na coleta (%s): %s", company_name, exc.orig or exc,
                    )
                    continue
                places_created_ids.append(str(new_lead.id) if new_lead.id is not None else None)
                collected_count += 1

                yield {
                    "type": "log",
                    "message": f"Coletado: {company_name}",
                    "timestamp": _ts(),
                }

                percent = 30 + int((i + 1) / len(batch_items) * 20)
                yield {"type": "progress", "step": "coleta", "percent": min(percent, 50)}

            db.commit()
            places_created_ids = [lid for lid in places_created_ids if lid]
            org_id = campaign.organization_id if campaign else None
            _dispatch_lead_created_webhooks(db, org_id, places_created_ids)
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

        # Template e perfil da vertical já resolvidos ANTES da coleta (o gate
        # de pre-scoring precisa deles) — ver bloco após a resolução de chaves.
        # Regras de calibração aprendidas com o time (docs/ai-feedback-loop.md):
        # carregadas uma vez por job e injetadas no prompt de cada scoring.
        learned_instructions: list = []
        if campaign and campaign.scoring_template_id:
            try:
                from services.learning_compilation_service import get_learning_rules
                learned_instructions = get_learning_rules(
                    db, campaign.organization_id, campaign.scoring_template_id,
                )
                if learned_instructions:
                    yield {
                        "type": "log",
                        "message": (
                            f"Ajustes aprendidos com o time aplicados "
                            f"({len(learned_instructions)} regras de calibração)."
                        ),
                        "timestamp": _ts(),
                    }
            except Exception as e:
                logger.warning("Falha ao carregar aprendizados da org: %s", e)

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
                leads_query = leads_query.filter(Lead.campaign_id.is_(None))
            if unscored_only:
                # Só o que ainda não pontuou (score NULL ou NOVO) — não
                # re-pontua QUALIFICADO/DESQUALIFICADO (economiza cota de IA).
                leads_query = leads_query.filter(
                    (Lead.qualification_score.is_(None)) | (Lead.status == LeadStatus.NOVO)
                )
            # Reanalisa leads da campanha (qualquer status prévio), sobrescrevendo
            # o scoring legado com o contextual novo. Respeita max_leads.
            leads_query = leads_query.order_by(Lead.created_at, Lead.id).limit(max_leads)
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
                leads_query = leads_query.filter(Lead.campaign_id.is_(None))
            # Ordem determinística (mais antigos primeiro) evita que a seleção
            # mude entre lotes e deixa leads NOVO sempre estáveis na fila.
            leads_query = leads_query.order_by(Lead.created_at, Lead.id).limit(max_leads)
            leads_to_process = leads_query.all()

        scored_count = 0
        failed_count = 0
        if not leads_to_process:
            yield {"type": "log", "message": "Nenhum lead novo para analisar", "timestamp": _ts()}
        else:
            total_to_process = len(leads_to_process)
            steps = resolve_enrichment_steps(scoring_template)
            use_tech_site = "technical_site" in steps
            use_cnpj_receita = "cnpj_receita" in steps

            for i, lead in enumerate(leads_to_process):
                yield {
                    "type": "log",
                    "message": f"Analisando: {lead.company_name}",
                    "timestamp": _ts(),
                }

                # Log granular por fonte de informação ativa (template)
                if not use_tech_site or not lead.website:
                    reason = "o template não pede auditoria de site" if not use_tech_site else "empresa sem website registrado"
                    yield {
                        "type": "log",
                        "message": f"Pulando auditoria de site para {lead.company_name} ({reason}).",
                        "timestamp": _ts(),
                    }
                else:
                    yield {
                        "type": "log",
                        "message": f"Auditando site ({lead.website})...",
                        "timestamp": _ts(),
                    }

                if use_cnpj_receita:
                    if lead.cnpj:
                        yield {
                            "type": "log",
                            "message": f"Buscando dados da empresa na Receita Federal (CNPJ)...",
                            "timestamp": _ts(),
                        }
                    else:
                        yield {
                            "type": "log",
                            "message": f"{lead.company_name} sem CNPJ cadastrado — seguindo sem dados da Receita.",
                            "timestamp": _ts(),
                        }

                _, scoring_result = await process_single_lead(
                    lead, enrichment_service, scoring_service, db,
                    analysis_profile=analysis_profile,
                    campaign_target_service=campaign.target_service if campaign else "",
                    campaign_target_segment=campaign.target_segment if campaign else "",
                    scoring_template=scoring_template,
                    allow_business_fallback=reanalyze_only,
                    learned_instructions=learned_instructions,
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
                        CompanyPersonService.sync_lead_entities(db, lead)
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

        # Leads NOVO que ainda aguardam pontuação (próximo lote) — publica no
        # resumo para a UI avisar "X na fila" em vez de parecer "score 0".
        queue_remaining = 0
        if not reanalyze_only:
            queue_filter = (Lead.status == LeadStatus.NOVO)
            if campaign:
                queue_filter = queue_filter & (Lead.campaign_id == campaign.id)
            else:
                queue_filter = queue_filter & (Lead.organization_id.is_(None))
            queue_remaining = db.query(Lead).filter(queue_filter).count()

        yield {
            "type": "done",
            "summary": {
                "collected": collected_count,
                "qualified": qualified,
                "scored": scored_count,
                "failed": failed_count,
                "total_processed": len(leads_to_process) if leads_to_process else 0,
                "queue_remaining": queue_remaining,
                "prescoring_discarded": prescoring_discarded,
                "prescoring_breakdown": prescoring_breakdown,
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
                "queue_remaining": queue_remaining,
                "prescoring_discarded": prescoring_discarded,
                "prescoring_breakdown": prescoring_breakdown,
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
