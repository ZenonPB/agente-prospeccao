from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import os
import sys
from pydantic import BaseModel, Field

from src.db.dependencies import get_db
from src.db.models import Campaign, CampaignStatus, Lead, LeadStatus, User, Job, JobStatus, JobType, Organization
from src.auth.dependencies import get_current_user, get_user_organization
from src.middleware.rate_limit import limiter
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
    porte_category: Optional[str] = Field(None, description="Filtro de porte: 'pequeno', 'medio', 'grande'")


class CollectPncpRequest(BaseModel):
    days_back: int = Field(30, ge=1, le=90, description="Janela de publicação de contratos (dias)")
    uf: Optional[str] = Field(None, min_length=2, max_length=2, description="Filtro por UF do órgão contratante")
    keyword: Optional[str] = Field(None, max_length=120, description="Palavra-chave no objeto do contrato")
    max_leads: int = Field(10, ge=1, le=100)


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
    scoring escolhido no wizard e ajustar os alvos."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    target_service: Optional[str] = Field(None, max_length=255)
    target_segment: Optional[str] = Field(None, max_length=100)
    target_city: Optional[str] = Field(None, max_length=100)
    target_state: Optional[str] = Field(None, max_length=2)
    target_country: Optional[str] = Field(None, max_length=100)
    analysis_profile: Optional[str] = Field(None, pattern="^(web_presence|business_opportunity)$")
    places_query: Optional[str] = Field(None, max_length=255)
    scoring_template_id: Optional[str] = Field(None)
    status: Optional[str] = Field(None, pattern="^(ACTIVE|PAUSED|COMPLETED|ARCHIVED)$")


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

    # N+1: agrega lead_count + avg_score de todos os leads das
    # campanhas da página numa única query GROUP BY.
    campaign_ids = [c.id for c in campaigns]
    stats = {}
    if campaign_ids:
        rows = (
            db.query(Lead.campaign_id, func.count(Lead.id), func.avg(Lead.qualification_score))
            .filter(Lead.campaign_id.in_(campaign_ids))
            .group_by(Lead.campaign_id)
            .all()
        )
        stats = {str(row[0]): (row[1], float(row[2] or 0)) for row in rows}

    result = []
    for campaign in campaigns:
        lead_count, avg_score = stats.get(str(campaign.id), (0, 0.0))
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
            "avg_score": round(avg_score, 1),
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
@limiter.limit("20/minute")
async def suggest_segment(
    request: Request,
    body: SuggestSegmentRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Sugere um segmento de prospecção via IA, baseado no perfil.

    - `profile=web_presence`        → tecnologia/serviços digitais.
    - `profile=business_opportunity` → engenharia/serviços industriais.

    O campo `exclude[]` permite que o frontend passe segmentos já sugeridos
    nesta sessão, evitando repetição imediata. Em caso de falha da LLM,
    retorna um fallback determinístico (offline-friendly).
    """
    from services.secret_service import SecretService
    from services.provider_client import quota_ok
    if not quota_ok(db, str(_org.id), "GROQ_API_KEY"):
        raise HTTPException(status_code=429, detail="Cota diária de IA esgotada — tente amanhã.")
    keys = await SecretService.resolve_all(db, str(_org.id))
    service = SegmentSuggestionService(api_key=keys.get("GROQ_API_KEY"))
    result = await service.suggest(
        profile=body.profile,
        current_segment=body.current_segment or "",
        exclude=body.exclude or [],
        db=db,
        organization_id=str(_org.id),
    )
    if not result.get("segment"):
        raise HTTPException(status_code=502, detail="Não foi possível gerar sugestão")
    return result


@router.post("/from-brief")
@limiter.limit("20/minute")
async def create_campaign_from_brief(
    request: Request,
    body: BriefCampaignRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Interpreta um brief em linguagem natural e devolve a campanha sugerida.

    O usuário descreve o que quer prospectar ("quero vender landing
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
    from services.secret_service import SecretService
    from services.template_router import route_scoring_template
    from services.provider_client import quota_ok
    from src.db.models import CampaignScoringTemplate

    if not quota_ok(db, str(_org.id), "GROQ_API_KEY"):
        raise HTTPException(status_code=429, detail="Cota diária de IA esgotada — tente amanhã.")

    keys = await SecretService.resolve_all(db, str(_org.id))
    service = CampaignBriefService(api_key=keys.get("GROQ_API_KEY"))
    try:
        suggestion = await service.interpret(
            body.brief, db=db, organization_id=str(_org.id),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    # Resolve o template de scoring mais próximo para o review card.
    template_info = await route_scoring_template(
        db,
        target_service=suggestion.get("target_service") or "",
        target_segment=suggestion.get("target_segment") or "",
        api_key=keys.get("GROQ_API_KEY"),
        organization_id=str(_org.id),
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
    — o pipeline passa a usar o template explícito em vez de
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

    # Pausar/retomar/arquivar pelo menu da campanha.
    if updates.get("status") is not None:
        from src.db.models import CampaignStatus
        try:
            campaign.status = CampaignStatus(updates["status"])
        except ValueError:
            raise HTTPException(status_code=422, detail="Status de campanha inválido")

    db.commit()
    db.refresh(campaign)
    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "scoring_template_id": str(campaign.scoring_template_id) if campaign.scoring_template_id else None,
    }


@router.post("/{campaign_id}/reanalyze")
@limiter.limit("10/minute")
async def reanalyze_campaign(
    request: Request,
    campaign_id: str,
    unscored_only: bool = Query(False, description="Reanalisa apenas leads sem score (score NULL ou status NOVO)"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Agenda a reanálise dos leads de uma campanha na fila de Jobs.

    A execução acontece no job-consumer (`jobs_consumer.py`), um job por vez;
    aqui a request só insere o Job e devolve `job_id` para o frontend escutar
    `/ws/pipeline/{job_id}` e consultar `GET /api/pipeline/jobs`.

    - Pula a coleta (reusa leads existentes).
    - Reseta scoring de cada lead (status=NOVO, fields limpos) internamente.
    - Usa o scoring contextual baseado em campaign.target_service/target_segment
      + fallback ao template 'Genérico'.
    - Com `unscored_only=True`, só os leads ainda sem pontuação relevante
      entram (score NULL ou status NOVO) — os já QUALIFICADO/DESQUALIFICADO
      ficam intocados (evita queimar cota de IA re-pontuando o que já pontuou).
    """
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == _org.id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    lead_filter = Lead.campaign_id == campaign.id
    if unscored_only:
        lead_filter = lead_filter & (
            (Lead.qualification_score.is_(None)) | (Lead.status == LeadStatus.NOVO)
        )
    lead_count = db.query(Lead).filter(lead_filter).count()
    if lead_count == 0:
        detail = (
            "Não há leads não pontuados para reanalisar"
            if unscored_only
            else "Campanha não tem leads para reanalisar"
        )
        raise HTTPException(status_code=400, detail=detail)

    job = Job(
        job_type=JobType.LEAD_ENRICHMENT,
        status=JobStatus.PENDING,
        campaign_id=campaign.id,
        organization_id=_org.id,
        payload={
            "campaign_id": str(campaign.id),
            "reanalyze_only": True,
            "unscored_only": unscored_only,
            "max_leads": lead_count,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return {"job_id": str(job.id), "status": "queued", "leads_to_reanalyze": lead_count}


# Limites de segurança do upload: 10 MB e 10.000 linhas.
MAX_CSV_BYTES = 10 * 1024 * 1024
MAX_CSV_ROWS = 10_000


@router.post("/{campaign_id}/import")
@limiter.limit("10/minute")
def import_campaign_csv(
    request: Request,
    campaign_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Importa leads para uma campanha a partir de um arquivo CSV (multipart/form-data).

    `def` síncrono (roda no threadpool do FastAPI) porque o parse + bulk_save
    são bloqueantes. Upload limitado a 10 MB / 10.000 linhas.
    """
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == _org.id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    if not file.filename.endswith(".csv") and file.content_type != "text/csv":
        raise HTTPException(status_code=400, detail="Apenas arquivos .csv são suportados")

    contents = file.file.read(MAX_CSV_BYTES + 1)
    if len(contents) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail=f"Arquivo maior que {MAX_CSV_BYTES // (1024 * 1024)} MB")

    try:
        text_content = contents.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text_content = contents.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="Não foi possível decodificar a codificação do arquivo CSV (use UTF-8 ou Latin-1).")

    if text_content.count("\n") > MAX_CSV_ROWS:
        raise HTTPException(status_code=413, detail=f"Arquivo com mais de {MAX_CSV_ROWS} linhas")

    result = CsvImportService.parse_and_import(
        db=db,
        campaign=campaign,
        file_content=text_content,
        user_id=user.id,
    )

    return result


@router.post("/{campaign_id}/collect-cnae")
@limiter.limit("10/minute")
async def collect_campaign_cnae(
    request: Request,
    campaign_id: str,
    data: CollectCnaeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Agenda a coleta/descoberta por CNAE / Receita Federal na fila de Jobs.

    Executado no job-consumer em background (um job por vez); a request só
    insere o Job e devolve o `job_id` para o WS / `GET /api/pipeline/jobs`.
    """
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
            "porte_category": data.porte_category,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return {"job_id": str(job.id), "status": "queued", "cnae_code": data.cnae_code}


@router.post("/{campaign_id}/collect-pncp")
@limiter.limit("10/minute")
async def collect_campaign_pncp(
    request: Request,
    campaign_id: str,
    data: CollectPncpRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Agenda a coleta de fornecedores de contratos públicos (PNCP).

    Executado no job-consumer em background; a request só insere o Job e
    devolve o `job_id` para o WS / `GET /api/pipeline/jobs`.
    """
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == _org.id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    from services.pncp_service import default_date_window

    pncp_start, pncp_end = default_date_window(days_back=data.days_back)

    job = Job(
        job_type=JobType.LEAD_COLLECTION,
        status=JobStatus.PENDING,
        campaign_id=campaign.id,
        organization_id=_org.id,
        payload={
            "campaign_id": str(campaign.id),
            "source": "pncp",
            "pncp_start": pncp_start,
            "pncp_end": pncp_end,
            "pncp_uf": (data.uf or "").upper() or None,
            "pncp_keyword": data.keyword,
            "max_leads": data.max_leads,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return {
        "job_id": str(job.id),
        "status": "queued",
        "pncp_start": pncp_start,
        "pncp_end": pncp_end,
    }


@router.get("/{campaign_id}/export/google-sheets")
def export_campaign_google_sheets(
    campaign_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Exporta os leads da campanha formatados para o Google Sheets (CSV)."""
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == _org.id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")

    leads = db.query(Lead).filter(Lead.campaign_id == campaign.id).all()

    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output, delimiter=",")
    writer.writerow([
        "ID Lead", "Nome Empresa", "CNPJ", "Website", "Telefone", "Cidade", "UF",
        "Score", "Prioridade", "Status", "Decisor Principal", "Email Decisor",
        "LinkedIn Decisor", "Necessidade Principal", "Gancho de Pitch", "Assunto Sugerido"
    ])

    for lead in leads:
        primary_contact = None
        for c in (lead.contacts or []):
            if c.is_primary:
                primary_contact = c
                break
        if not primary_contact and lead.contacts:
            primary_contact = lead.contacts[0]

        writer.writerow([
            str(lead.id),
            lead.company_name or lead.name or "",
            lead.cnpj or "",
            lead.website or "",
            lead.phone or "",
            lead.city or "",
            lead.state or "",
            lead.qualification_score or 0,
            lead.priority.value if lead.priority else "",
            lead.status.value if lead.status else "",
            primary_contact.name if primary_contact else "",
            primary_contact.email if primary_contact else "",
            primary_contact.linkedin_url if primary_contact else "",
            lead.primary_need or "",
            lead.pitch_angle or "",
            lead.suggested_subject or "",
        ])

    csv_data = output.getvalue()
    filename = f"campaign_{campaign_id}_export.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


class GoogleSheetsSyncPayload(BaseModel):
    spreadsheet_id: Optional[str] = None


@router.post("/{campaign_id}/sync-google-sheets")
async def sync_campaign_google_sheets(
    campaign_id: str,
    data: Optional[GoogleSheetsSyncPayload] = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
):
    """Sincroniza e espelha os leads da campanha diretamente em uma planilha do Google Sheets via OAuth2."""
    from services.google_sheets_service import GoogleSheetsService

    spreadsheet_id = data.spreadsheet_id if data else None
    res = await GoogleSheetsService.sync_campaign_to_sheets(
        db=db,
        organization_id=_org.id,
        campaign_id=campaign_id,
        spreadsheet_id=spreadsheet_id,
    )

    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Falha na sincronização com Google Sheets"))

    return res
