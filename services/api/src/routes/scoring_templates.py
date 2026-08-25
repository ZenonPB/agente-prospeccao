from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import os
import sys

from src.db.dependencies import get_db
from src.db.models import Campaign, CampaignScoringTemplate, User, Organization, OrganizationMember
from src.auth.dependencies import get_current_user, get_user_organization, require_manager
from src.middleware.rate_limit import limiter

# Importa o serviço de geração dos workers (reaproveitando a fonte única).
_workers_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "workers", "src")
if _workers_path not in sys.path:
    sys.path.insert(0, _workers_path)

router = APIRouter(prefix="/scoring-templates", tags=["scoring-templates"])

# Fontes de informação de uma empresa usadas na avaliação do lead.
ENRICHMENT_STEP_KEYS = {"technical_site", "cnpj_receita", "business_social"}


class Signal(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    weight_hint: str = Field("medium", pattern="^(high|medium|low)$")


class Playbook(BaseModel):
    """Playbook de outreach por vertical."""
    hooks: List[str] = Field(default_factory=list)
    subject_ideas: List[str] = Field(default_factory=list)
    objections: List[dict] = Field(default_factory=list)
    # Eixo de conteúdo por etapa da cadência (educativo → caso → proposta).
    stage_angles: Optional[dict] = None


class CreateScoringTemplateRequest(BaseModel):
    service_label: str = Field(..., min_length=1, max_length=255)
    positive_signals: List[Signal] = Field(default_factory=list)
    negative_signals: List[Signal] = Field(default_factory=list)
    context_signals: List[Signal] = Field(default_factory=list)
    requires_technical_report: bool = True
    requires_business_data: bool = True
    enrichment_steps: Optional[List[str]] = None
    cadence_schedule: Optional[List[int]] = None
    extra_instructions: Optional[str] = Field(None, max_length=4000)
    playbook: Optional[Playbook] = None
    # Duplicar uma vertente existente (global ou da org) como ponto de partida.
    # Sem isso, a criação parte dos critérios em branco.
    source_template_id: Optional[str] = None

    @field_validator("enrichment_steps")
    @classmethod
    def _validate_steps(cls, v):
        if v is None:
            return None
        invalid = [s for s in v if s not in ENRICHMENT_STEP_KEYS]
        if invalid:
            raise ValueError(f"fontes de informação inválidas: {invalid}")
        return list(dict.fromkeys(v))

    @field_validator("cadence_schedule")
    @classmethod
    def _validate_schedule(cls, v):
        if v is None:
            return None
        if len(v) != 4:
            raise ValueError("o acompanhamento precisa de exatamente 4 dias")
        if any(not isinstance(d, int) or d < 0 for d in v):
            raise ValueError("os dias devem ser inteiros maiores ou iguais a 0")
        return v


class GenerateScoringTemplateRequest(BaseModel):
    """Corpo do POST /scoring-templates/generate.

    `service` é a oferta (ex.: "manutenção de compressores") e `description`
    contextualiza quem é o público-alvo, em linguagem natural — usados para a
    IA propor os critérios. O resultado é um rascunho (`is_generated=True`).
    """
    service: str = Field(..., min_length=2, max_length=255)
    segment: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)


class PatchScoringTemplateRequest(BaseModel):
    service_label: Optional[str] = Field(None, min_length=1, max_length=255)
    positive_signals: Optional[List[Signal]] = None
    negative_signals: Optional[List[Signal]] = None
    context_signals: Optional[List[Signal]] = None
    requires_technical_report: Optional[bool] = None
    requires_business_data: Optional[bool] = None
    enrichment_steps: Optional[List[str]] = None
    cadence_schedule: Optional[List[int]] = None
    extra_instructions: Optional[str] = Field(None, max_length=4000)
    is_active: Optional[bool] = None
    playbook: Optional[Playbook] = None

    @field_validator("enrichment_steps")
    @classmethod
    def _validate_steps(cls, v):
        if v is None:
            return None
        invalid = [s for s in v if s not in ENRICHMENT_STEP_KEYS]
        if invalid:
            raise ValueError(f"fontes de informação inválidas: {invalid}")
        return list(dict.fromkeys(v))

    @field_validator("cadence_schedule")
    @classmethod
    def _validate_schedule(cls, v):
        if v is None:
            return None
        if len(v) != 4:
            raise ValueError("o acompanhamento precisa de exatamente 4 dias")
        if any(not isinstance(d, int) or d < 0 for d in v):
            raise ValueError("os dias devem ser inteiros maiores ou iguais a 0")
        return v


def _serialize(tmpl: CampaignScoringTemplate) -> dict:
    return {
        "id": str(tmpl.id),
        "service_label": tmpl.service_label,
        "positive_signals": tmpl.positive_signals or [],
        "negative_signals": tmpl.negative_signals or [],
        "context_signals": tmpl.context_signals or [],
        "requires_technical_report": tmpl.requires_technical_report,
        "requires_business_data": tmpl.requires_business_data,
        "enrichment_steps": getattr(tmpl, "enrichment_steps", None) or None,
        "cadence_schedule": getattr(tmpl, "cadence_schedule", None) or None,
        "extra_instructions": tmpl.extra_instructions,
        "playbook": tmpl.playbook or {},
        "is_generated": tmpl.is_generated,
        "is_active": tmpl.is_active,
        "organization_id": str(tmpl.organization_id) if tmpl.organization_id else None,
        "created_at": tmpl.created_at.isoformat() if tmpl.created_at else None,
        "updated_at": tmpl.updated_at.isoformat() if tmpl.updated_at else None,
    }


def _playbook_dict(pb) -> dict:
    if pb is None:
        return {}
    if isinstance(pb, Playbook):
        return pb.model_dump()
    return {
        "hooks": pb.get("hooks") or [],
        "subject_ideas": pb.get("subject_ideas") or [],
        "objections": pb.get("objections") or [],
        "stage_angles": pb.get("stage_angles") or None,
    }


def _to_signal_dicts(signals) -> list:
    """Normaliza sinais para o formato JSONB persistido.

    Aceita objetos `Signal` (pydantic) ou dicts (já desnormalizados por
    `model_dump`) — o PATCH usa `model_dump(exclude_unset=True)`, que entrega
    dicts; o POST entrega instâncias de `Signal`.
    """
    result = []
    for s in signals:
        if isinstance(s, Signal):
            result.append({
                "label": s.label,
                "description": s.description,
                "weight_hint": s.weight_hint,
            })
        else:
            result.append({
                "label": s.get("label", ""),
                "description": s.get("description"),
                "weight_hint": s.get("weight_hint", "medium"),
            })
    return result


def _template_query(db: Session, template_id: str, org_id) -> Optional[CampaignScoringTemplate]:
    """Busca um template visível à org (global ou da própria org)."""
    return db.query(CampaignScoringTemplate).filter(
        CampaignScoringTemplate.id == template_id,
        (CampaignScoringTemplate.organization_id.is_(None)) |
        (CampaignScoringTemplate.organization_id == org_id),
    ).first()


def _label_conflict(db: Session, label: str, org_id) -> bool:
    return db.query(CampaignScoringTemplate).filter(
        (CampaignScoringTemplate.service_label == label) &
        ((CampaignScoringTemplate.organization_id.is_(None)) |
         (CampaignScoringTemplate.organization_id == org_id)),
    ).first() is not None


@router.get("")
def list_scoring_templates(
    scope: str = Query("all", pattern="^(all|global|org)$"),
    include_inactive: bool = Query(False),
    search: Optional[str] = Query(None, max_length=100),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
):
    """Lista templates de scoring.

    - `scope=all`   → globais (organization_id NULL) + da org do usuário.
    - `scope=global` → apenas globais/seeds.
    - `scope=org`   → apenas os da org do usuário (inclui gerados).

    `search` filtra por service_label (accent-insensitive via ILIKE).
    """
    query = db.query(CampaignScoringTemplate)

    if scope == "global":
        query = query.filter(CampaignScoringTemplate.organization_id.is_(None))
    elif scope == "org":
        query = query.filter(CampaignScoringTemplate.organization_id == org.id)
    else:  # all
        query = query.filter(
            (CampaignScoringTemplate.organization_id.is_(None)) |
            (CampaignScoringTemplate.organization_id == org.id)
        )

    if not include_inactive:
        query = query.filter(CampaignScoringTemplate.is_active.is_(True))

    if search:
        query = query.filter(CampaignScoringTemplate.service_label.ilike(f"%{search}%"))

    templates = query.order_by(CampaignScoringTemplate.service_label.asc()).all()
    return {"total": len(templates), "templates": [_serialize(t) for t in templates]}


@router.get("/{template_id}")
def get_scoring_template(
    template_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
):
    tmpl = _template_query(db, template_id, org.id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template não encontrado")
    return _serialize(tmpl)


@router.post("", status_code=201)
def create_scoring_template(
    body: CreateScoringTemplateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(require_manager()),
):
    """Cria uma vertente na org do usuário (escopo local).

    `source_template_id` opcional duplica uma vertente existente (global ou da
    própria org) como ponto de partida — o fluxo mais comum para personalizar
    uma vertente de fábrica para o ICP próprio. Critérios explícitos no body
    têm precedência sobre a fonte. A chave natural `service_label` é única por
    org — duplicar label dentro da mesma org retorna 409.
    """
    updates = body.model_dump(exclude_unset=True)

    if body.source_template_id:
        source = _template_query(db, body.source_template_id, org.id)
        if not source:
            raise HTTPException(status_code=404, detail="Vertente de origem não encontrada")
        fields = {
            "positive_signals": source.positive_signals or [],
            "negative_signals": source.negative_signals or [],
            "context_signals": source.context_signals or [],
            "requires_technical_report": source.requires_technical_report,
            "requires_business_data": source.requires_business_data,
            "enrichment_steps": source.enrichment_steps,
            "cadence_schedule": source.cadence_schedule,
            "extra_instructions": source.extra_instructions,
            "playbook": source.playbook or {},
        }
        fields.update({k: v for k, v in updates.items() if k not in ("source_template_id",)})
    else:
        fields = {
            "positive_signals": _to_signal_dicts(body.positive_signals),
            "negative_signals": _to_signal_dicts(body.negative_signals),
            "context_signals": _to_signal_dicts(body.context_signals),
            "requires_technical_report": body.requires_technical_report,
            "requires_business_data": body.requires_business_data,
            "enrichment_steps": body.enrichment_steps,
            "cadence_schedule": body.cadence_schedule,
            "extra_instructions": body.extra_instructions,
            "playbook": _playbook_dict(body.playbook),
        }

    label = updates.get("service_label", body.service_label)
    if _label_conflict(db, label, org.id):
        raise HTTPException(status_code=409, detail="Já existe uma vertente com este nome")

    tmpl = CampaignScoringTemplate(
        service_label=label,
        positive_signals=fields["positive_signals"],
        negative_signals=fields["negative_signals"],
        context_signals=fields["context_signals"],
        requires_technical_report=fields["requires_technical_report"],
        requires_business_data=fields["requires_business_data"],
        enrichment_steps=fields["enrichment_steps"],
        cadence_schedule=fields["cadence_schedule"],
        extra_instructions=fields["extra_instructions"],
        playbook=fields["playbook"],
        is_active=True,
        organization_id=org.id,
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return _serialize(tmpl)


@router.post("/generate", status_code=201)
@limiter.limit("15/minute")
async def generate_scoring_template(
    request: Request,
    body: GenerateScoringTemplateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(require_manager()),
):
    """Gera uma vertente por IA como rascunho (`is_generated=True`, inativa).

    A IA propõe critérios, fontes de informação e instruções para a oferta
    `service`/`segment`/`description`; o rascunho já é persistido para o
    usuário refinar no editor e ativar quando estiver bom. Sem persistência
    prévia, um clique acidental apagaria o trabalho — persiste direto.
    """
    from services.provider_client import quota_ok
    from services.secret_service import SecretService
    from services.template_generation_service import TemplateGenerationService

    if not quota_ok(db, str(org.id), "GROQ_API_KEY"):
        raise HTTPException(status_code=429, detail="Cota diária de IA esgotada — tente amanhã.")

    keys = await SecretService.resolve_all(db, str(org.id))
    service = TemplateGenerationService(api_key=keys.get("GROQ_API_KEY"))
    generated = await service.build_draft(
        db,
        body.service,
        body.segment or "",
        body.description or "",
        organization_id=str(org.id),
    )
    if not generated:
        raise HTTPException(status_code=502, detail="Não foi possível gerar os critérios agora. Tente novamente.")

    label = generated["service_label"]
    if _label_conflict(db, label, org.id):
        raise HTTPException(status_code=409, detail=f"Já existe uma vertente chamada \"{label}\"")

    tmpl = CampaignScoringTemplate(
        service_label=label,
        positive_signals=generated["positive_signals"],
        negative_signals=generated["negative_signals"],
        context_signals=generated["context_signals"],
        requires_technical_report=generated["requires_technical_report"],
        requires_business_data=generated["requires_business_data"],
        enrichment_steps=generated.get("enrichment_steps"),
        cadence_schedule=generated.get("cadence_schedule"),
        extra_instructions=generated.get("extra_instructions"),
        playbook={},
        is_generated=True,
        is_active=False,
        organization_id=org.id,
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return _serialize(tmpl)


@router.patch("/{template_id}")
def patch_scoring_template(
    template_id: str,
    body: PatchScoringTemplateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(require_manager()),
):
    """Atualiza uma vertente da org do usuário (ou global, se compartilhada).

    Usado tanto para o editor de critérios no wizard quanto para a revisão
    humana de rascunhos gerados — o usuário pode ajustar critérios/flags/
    instruções antes de ativar em massa.
    """
    tmpl = _template_query(db, template_id, org.id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template não encontrado")
    if tmpl.organization_id is None:
        # Seeds globais são compartilhados entre todas as orgs — edição por um
        # usuário afetaria o scoring de todos. Para personalizar, duplique.
        raise HTTPException(
            status_code=400,
            detail="Template global de fábrica — duplique para personalizar.",
        )

    updates = body.model_dump(exclude_unset=True)
    if "service_label" in updates:
        new_label = updates["service_label"]
        existing = db.query(CampaignScoringTemplate).filter(
            (CampaignScoringTemplate.service_label == new_label) &
            (CampaignScoringTemplate.id != tmpl.id),
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Já existe uma vertente com este nome")
        tmpl.service_label = new_label
    if "positive_signals" in updates:
        tmpl.positive_signals = _to_signal_dicts(updates["positive_signals"])
    if "negative_signals" in updates:
        tmpl.negative_signals = _to_signal_dicts(updates["negative_signals"])
    if "context_signals" in updates:
        tmpl.context_signals = _to_signal_dicts(updates["context_signals"])
    if "requires_technical_report" in updates:
        tmpl.requires_technical_report = updates["requires_technical_report"]
    if "requires_business_data" in updates:
        tmpl.requires_business_data = updates["requires_business_data"]
    if "enrichment_steps" in updates:
        tmpl.enrichment_steps = updates["enrichment_steps"] or None
    if "cadence_schedule" in updates:
        tmpl.cadence_schedule = updates["cadence_schedule"] or None
    if "extra_instructions" in updates:
        tmpl.extra_instructions = updates["extra_instructions"]
    if "is_active" in updates:
        tmpl.is_active = updates["is_active"]
    if "playbook" in updates and updates["playbook"] is not None:
        tmpl.playbook = _playbook_dict(updates["playbook"])

    db.commit()
    db.refresh(tmpl)
    return _serialize(tmpl)


@router.delete("/{template_id}")
def delete_scoring_template(
    template_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
    member: OrganizationMember = Depends(require_manager()),
):
    """Remove uma vertente criada pela própria org (globais são protegidas).

    Vertentes em uso por alguma campanha não podem ser removidas — retorna 409
    para o usuário reativá-la ou trocar a campanha de vertente.
    """
    tmpl = db.query(CampaignScoringTemplate).filter(
        CampaignScoringTemplate.id == template_id,
        CampaignScoringTemplate.organization_id == org.id,
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template não encontrado")

    in_use = db.query(Campaign).filter(Campaign.scoring_template_id == tmpl.id).count()
    if in_use:
        raise HTTPException(
            status_code=409,
            detail=f"Esta vertente está em uso em {in_use} campanha(s). Troque a vertente nas campanhas antes de remover.",
        )

    db.delete(tmpl)
    db.commit()
    return {"deleted": True, "id": str(tmpl.id)}