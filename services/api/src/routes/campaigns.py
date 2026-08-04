from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import os
import sys
from pydantic import BaseModel, Field

from src.db.dependencies import get_db
from src.db.models import Campaign, CampaignStatus, Lead, User, Job, JobStatus, JobType, Organization
from src.auth.dependencies import get_current_user, get_user_organization
from src.services.csv_import_service import CsvImportService

# Importa o serviço de sugestão de segmentos dos workers (reaproveitando a fonte única).
_workers_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "workers", "src")
if _workers_path not in sys.path:
    sys.path.insert(0, _workers_path)
from services.segment_suggestion_service import SegmentSuggestionService  # noqa: E402

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


class CreateCampaignRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    target_service: Optional[str] = None
    target_segment: Optional[str] = None
    target_city: Optional[str] = None
    target_state: Optional[str] = None
    target_country: Optional[str] = None
    analysis_profile: str = "web_presence"
    places_query: Optional[str] = Field(None, max_length=255)


class BriefCampaignRequest(BaseModel):
    """Corpo do POST /api/campaigns/from-brief.

    `brief` é a intenção em linguagem natural (pt-BR), ex.:
    "quero vender landing pages para clínicas de psicologia em Araraquara".
    """
    brief: str = Field(..., min_length=3, max_length=1000)


class CollectCnaeRequest(BaseModel):
    cnae_code: Optional[str] = Field(None, description="Código CNAE (ex: '2869100' ou '28.69-1-00')")
    cnpjs: Optional[List[str]] = Field(None, description="Lista de CNPJs a buscar/validar")
    max_leads: int = Field(20, ge=1, le=100)


class SuggestSegmentRequest(BaseModel):
    """Corpo do POST /api/campaigns/suggest-segment.

    `profile` deve ser `web_presence` ou `business_opportunity` (mesmos
    valores de `Campaign.analysis_profile`). Os demais campos são
    opcionais e ajudam a variar as sugestões sem repetir.
    """
    profile: str = Field("web_presence", pattern="^(web_presence|business_opportunity)$")
    current_segment: Optional[str] = Field(None, max_length=120)
    exclude: Optional[List[str]] = Field(None, max_length=20)


class PatchCampaignRequest(BaseModel):
    """Atualização parcial de campanha — usado para vincular o template de
    scoring escolhido no wizard (item 1.5.3) e ajustar os alvos."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    target_service: Optional[str] = Field(None, max_length=255)
    target_segment: Optional[str] = Field(None, max_length=100)
    target_city: Optional[str] = Field(None, max_length=100)
    target_state: Optional[str] = Field(None, max_length=2)
    target_country: Optional[str] = Field(None, max_length=100)
    analysis_profile: Optional[str] = Field(None, pattern="^(web_presence|business_opportunity)$")
    places_query: Optional[str] = Field(None, max_length=255)
    scoring_template_id: Optional[str] = Field(None)


@router.get("")
def list_campaigns(
    status: Optional[str] = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    query = db.query(Campaign).filter(Campaign.organization_id == _org.id)

    if status:
        query = query.filter(Campaign.status == status)

    total = query.count()
    campaigns = query.order_by(Campaign.created_at.desc()).offset(offset).limit(limit).all()

    result = []
    for campaign in campaigns:
        lead_count = db.query(Lead).filter(Lead.campaign_id == campaign.id).count()
        avg_score = 0
        if lead_count > 0:
            avg_score = db.query(func.avg(Lead.qualification_score)).filter(Lead.campaign_id == campaign.id).scalar() or 0

        result.append({
            "id": str(campaign.id),
            "name": campaign.name,
            "target_service": campaign.target_service,
            "target_segment": campaign.target_segment,
            "target_city": campaign.target_city,
            "target_state": campaign.target_state,
            "target_country": campaign.target_country,
            "analysis_profile": campaign.analysis_profile.value if campaign.analysis_profile else "web_presence",
            "status": campaign.status.value if campaign.status else None,
            "places_query": campaign.places_query,
            "lead_count": lead_count,
            "avg_score": round(float(avg_score), 1),
            "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
            "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
        })

    return {
        "total": total,
        "campaigns": result,
    }


@router.post("", status_code=201)
def create_campaign(
    request: CreateCampaignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    campaign = Campaign(
        user_id=user.id,
        organization_id=_org.id,
        name=request.name,
        target_service=request.target_service,
        target_segment=request.target_segment,
        target_city=request.target_city,
        target_state=request.target_state,
        target_country=request.target_country or "Brasil",
        analysis_profile=request.analysis_profile,
        places_query=request.places_query,
        status=CampaignStatus.ACTIVE,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return {
        "id": str(campaign.id),
        "user_id": str(campaign.user_id),
        "name": campaign.name,
        "target_service": campaign.target_service,
        "target_segment": campaign.target_segment,
        "target_city": campaign.target_city,
        "target_state": campaign.target_state,
        "target_country": campaign.target_country,
        "analysis_profile": campaign.analysis_profile.value if campaign.analysis_profile else "web_presence",
        "status": campaign.status.value if campaign.status else None,
        "places_query": campaign.places_query,
        "lead_count": 0,
        "avg_score": 0,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
    }


@router.post("/suggest-segment")
async def suggest_segment(
    body: SuggestSegmentRequest,
    _user: User = Depends(get_current_user),
):
    """Sugere um segmento de prospecção via IA, baseado no perfil.

    - `profile=web_presence`        → tecnologia/serviços digitais.
    - `profile=business_opportunity` → engenharia/serviços industriais.

    O campo `exclude[]` permite que o frontend passe segmentos já sugeridos
    nesta sessão, evitando repetição imediata. Em caso de falha da LLM,
    retorna um fallback determinístico (offline-friendly).
    """
    service = SegmentSuggestionService()
    result = await service.suggest(
        profile=body.profile,
        current_segment=body.current_segment or "",
        exclude=body.exclude or [],
    )
    if not result.get("segment"):
        raise HTTPException(status_code=502, detail="Não foi possível gerar sugestão")
    return result


@router.post("/from-brief")
async def create_campaign_from_brief(
    body: BriefCampaignRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Interpreta um brief em linguagem natural e devolve a campanha sugerida.

    Item 1.4: o usuário descreve o que quer prospectar ("quero vender landing
    pages para clínicas de psicologia em Araraquara") e a IA devolve os campos
    estruturados (name, target_service, target_segment, target_city,
    target_state, analysis_profile, places_query) + rationale.

    NÃO cria a campanha — o usuário revisa/edita os campos e confirma via
    `POST /api/campaigns`. Também resolve o template de scoring mais próximo
    (matched via router exact/fuzzy/LLM), semelhante ao que o pipeline fará,
    para o review card exibir qual template será usado.
    """
    # Importa o serviço dos workers (fonte única) e o router de template.
    from services.campaign_brief_service import CampaignBriefService
    from services.template_router import route_scoring_template
    from src.db.models import CampaignScoringTemplate

    service = CampaignBriefService()
    try:
        suggestion = await service.interpret(body.brief)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    # Resolve o template de scoring mais próximo para o review card.
    template_info = await route_scoring_template(
        db,
        target_service=suggestion.get("target_service") or "",
        target_segment=suggestion.get("target_segment") or "",
    )
    scoring_template_id = None
    scoring_template_label = None
    if template_info.get("template") and template_info.get("matched_label"):
        matched_label = template_info["matched_label"]
        tmpl = db.query(CampaignScoringTemplate).filter(
            CampaignScoringTemplate.service_label == matched_label,
            CampaignScoringTemplate.is_active.is_(True),
        ).first()
        if tmpl:
            scoring_template_id = str(tmpl.id)
            scoring_template_label = tmpl.service_label

    return {
        **suggestion,
        "scoring_template_id": scoring_template_id,
        "scoring_template_label": scoring_template_label,
        "template_route": template_info.get("route"),
    }


@router.get("/{campaign_id}")
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == _org.id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    lead_count = db.query(Lead).filter(Lead.campaign_id == campaign.id).count()
    avg_score = db.query(func.avg(Lead.qualification_score)).filter(Lead.campaign_id == campaign.id).scalar() or 0

    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "target_service": campaign.target_service,
        "target_segment": campaign.target_segment,
        "target_city": campaign.target_city,
        "target_state": campaign.target_state,
        "target_country": campaign.target_country,
        "analysis_profile": campaign.analysis_profile.value if campaign.analysis_profile else "web_presence",
        "status": campaign.status.value if campaign.status else None,
        "places_query": campaign.places_query,
        "scoring_template_id": str(campaign.scoring_template_id) if campaign.scoring_template_id else None,
        "lead_count": lead_count,
        "avg_score": round(float(avg_score), 1),
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
    }


@router.patch("/{campaign_id}")
def patch_campaign(
    campaign_id: str,
    body: PatchCampaignRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Atualiza parcialmente uma campanha da org do usuário.

    `scoring_template_id` vincula o template de critérios escolhido no wizard
    (item 1.5.3) — o pipeline passa a usar o template explícito em vez de
    rotear. Valida que o template pertence à org ou é global.
    """
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == _org.id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    updates = body.model_dump(exclude_unset=True)

    if updates.get("scoring_template_id") is not None:
        from src.db.models import CampaignScoringTemplate
        tmpl = db.query(CampaignScoringTemplate).filter(
            CampaignScoringTemplate.id == updates["scoring_template_id"],
            (CampaignScoringTemplate.organization_id.is_(None)) |
            (CampaignScoringTemplate.organization_id == _org.id),
        ).first()
        if not tmpl:
            raise HTTPException(status_code=404, detail="Template de scoring não encontrado")
        campaign.scoring_template_id = tmpl.id
    elif "scoring_template_id" in updates:
        # Permite desvincular (scoring_template_id=null → router decide).
        campaign.scoring_template_id = None

    for field in ("name", "target_service", "target_segment", "target_city",
                  "target_state", "target_country", "places_query"):
        if field in updates:
            setattr(campaign, field, updates[field])

    if "analysis_profile" in updates:
        campaign.analysis_profile = updates["analysis_profile"]

    db.commit()
    db.refresh(campaign)
    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "scoring_template_id": str(campaign.scoring_template_id) if campaign.scoring_template_id else None,
    }


@router.post("/{campaign_id}/reanalyze")
async def reanalyze_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Dispara reanálise de TODOS os leads de uma campanha usando o pipeline
    contextual novo.

    - Pula a coleta (reusa leads existentes).
    - Reseta scoring de cada lead (status=NOVO, fields limpos) internamente.
    - Usa o scoring contextual baseado em campaign.target_service/target_segment
      + fallback ao template 'Genérico'.

    Retorna `{job_id}` para que o frontend possa escutar /ws/pipeline/{job_id}.
    """
    import asyncio
    from src.pipeline_worker import run_pipeline
    from src.routes.pipeline import active_connections

    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == _org.id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    lead_count = db.query(Lead).filter(Lead.campaign_id == campaign.id).count()
    if lead_count == 0:
        raise HTTPException(status_code=400, detail="Campanha não tem leads para reanalisar")

    job = Job(
        job_type=JobType.LEAD_ENRICHMENT,
        status=JobStatus.PENDING,
        campaign_id=campaign.id,
        organization_id=_org.id,
        payload={
            "campaign_id": str(campaign.id),
            "reanalyze_only": True,
            "max_leads": lead_count,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    job_id = str(job.id)

    async def _runner():
        try:
            async for event in run_pipeline(
                job_id=job_id, query=None, campaign_id=str(campaign.id),
                max_leads=lead_count, reanalyze_only=True,
            ):
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
            import logging
            logging.getLogger(__name__).error("Reanalyze task error: %s", e)

    asyncio.create_task(_runner())

    return {"job_id": job_id, "status": "started", "leads_to_reanalyze": lead_count}


@router.post("/{campaign_id}/import")
async def import_campaign_csv(
    campaign_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Importa leads para uma campanha a partir de um arquivo CSV (multipart/form-data)."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == _org.id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    if not file.filename.endswith(".csv") and file.content_type != "text/csv":
        raise HTTPException(status_code=400, detail="Apenas arquivos .csv são suportados")

    contents = await file.read()
    try:
        text_content = contents.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text_content = contents.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="Não foi possível decodificar a codificação do arquivo CSV (use UTF-8 ou Latin-1).")

    result = CsvImportService.parse_and_import(
        db=db,
        campaign=campaign,
        file_content=text_content,
        user_id=user.id,
    )

    return result


@router.post("/{campaign_id}/collect-cnae")
async def collect_campaign_cnae(
    campaign_id: str,
    data: CollectCnaeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Inicia a coleta/descoberta de empresas por CNAE / Receita Federal para uma campanha."""
    import asyncio
    from src.pipeline_worker import run_pipeline
    from src.routes.pipeline import active_connections

    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == _org.id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    job = Job(
        job_type=JobType.LEAD_COLLECTION,
        status=JobStatus.PENDING,
        campaign_id=campaign.id,
        organization_id=_org.id,
        payload={
            "campaign_id": str(campaign.id),
            "source": "cnae",
            "cnae_code": data.cnae_code,
            "cnpjs": data.cnpjs,
            "max_leads": data.max_leads,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    job_id = str(job.id)

    async def _runner():
        try:
            async for event in run_pipeline(
                job_id=job_id,
                campaign_id=str(campaign.id),
                max_leads=data.max_leads,
                source="cnae",
                cnae_code=data.cnae_code,
                cnpjs=data.cnpjs,
            ):
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
            import logging
            logging.getLogger(__name__).error("CNAE collection task error: %s", e)

    asyncio.create_task(_runner())

    return {"job_id": job_id, "status": "started", "cnae_code": data.cnae_code}
