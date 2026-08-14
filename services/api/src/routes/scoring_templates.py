from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional

from src.db.dependencies import get_db
from src.db.models import CampaignScoringTemplate, User, Organization
from src.auth.dependencies import get_current_user, get_user_organization

router = APIRouter(prefix="/scoring-templates", tags=["scoring-templates"])


class Signal(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    weight_hint: str = Field("medium", pattern="^(high|medium|low)$")


class Playbook(BaseModel):
    """Playbook de outreach por vertical."""
    hooks: List[str] = Field(default_factory=list)
    subject_ideas: List[str] = Field(default_factory=list)
    objections: List[dict] = Field(default_factory=list)


class CreateScoringTemplateRequest(BaseModel):
    service_label: str = Field(..., min_length=1, max_length=255)
    positive_signals: List[Signal] = Field(default_factory=list)
    negative_signals: List[Signal] = Field(default_factory=list)
    context_signals: List[Signal] = Field(default_factory=list)
    requires_technical_report: bool = True
    requires_business_data: bool = True
    extra_instructions: Optional[str] = Field(None, max_length=4000)
    playbook: Optional[Playbook] = None


class PatchScoringTemplateRequest(BaseModel):
    service_label: Optional[str] = Field(None, min_length=1, max_length=255)
    positive_signals: Optional[List[Signal]] = None
    negative_signals: Optional[List[Signal]] = None
    context_signals: Optional[List[Signal]] = None
    requires_technical_report: Optional[bool] = None
    requires_business_data: Optional[bool] = None
    extra_instructions: Optional[str] = Field(None, max_length=4000)
    is_active: Optional[bool] = None
    playbook: Optional[Playbook] = None


def _serialize(tmpl: CampaignScoringTemplate) -> dict:
    return {
        "id": str(tmpl.id),
        "service_label": tmpl.service_label,
        "positive_signals": tmpl.positive_signals or [],
        "negative_signals": tmpl.negative_signals or [],
        "context_signals": tmpl.context_signals or [],
        "requires_technical_report": tmpl.requires_technical_report,
        "requires_business_data": tmpl.requires_business_data,
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
    tmpl = db.query(CampaignScoringTemplate).filter(
        CampaignScoringTemplate.id == template_id,
        (CampaignScoringTemplate.organization_id.is_(None)) |
        (CampaignScoringTemplate.organization_id == org.id),
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template não encontrado")
    return _serialize(tmpl)


@router.post("", status_code=201)
def create_scoring_template(
    body: CreateScoringTemplateRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
):
    """Cria um template na org do usuário (escopo local).

    Templates criados manualmente são `is_generated=False`. A chave natural
    `service_label` é única por org — duplicar label dentro da mesma org
    retorna 409.
    """
    existing = db.query(CampaignScoringTemplate).filter(
        (CampaignScoringTemplate.service_label == body.service_label) &
        ((CampaignScoringTemplate.organization_id.is_(None)) |
         (CampaignScoringTemplate.organization_id == org.id)),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Já existe um template com este label")

    tmpl = CampaignScoringTemplate(
        service_label=body.service_label,
        positive_signals=_to_signal_dicts(body.positive_signals),
        negative_signals=_to_signal_dicts(body.negative_signals),
        context_signals=_to_signal_dicts(body.context_signals),
        requires_technical_report=body.requires_technical_report,
        requires_business_data=body.requires_business_data,
        extra_instructions=body.extra_instructions,
        playbook=_playbook_dict(body.playbook),
        is_active=True,
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
):
    """Atualiza um template da org do usuário (ou global, se compartilhado).

    Usado tanto para o editor de sinais no wizard quanto para a
    revisão humana de templates gerados — o usuário pode editar
    sinais/flags/instruções antes de ativar em massa.
    """
    tmpl = db.query(CampaignScoringTemplate).filter(
        CampaignScoringTemplate.id == template_id,
        (CampaignScoringTemplate.organization_id.is_(None)) |
        (CampaignScoringTemplate.organization_id == org.id),
    ).first()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template não encontrado")

    updates = body.model_dump(exclude_unset=True)
    if "service_label" in updates:
        tmpl.service_label = updates["service_label"]
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
    if "extra_instructions" in updates:
        tmpl.extra_instructions = updates["extra_instructions"]
    if "is_active" in updates:
        tmpl.is_active = updates["is_active"]
    if "playbook" in updates and updates["playbook"] is not None:
        tmpl.playbook = _playbook_dict(updates["playbook"])

    db.commit()
    db.refresh(tmpl)
    return _serialize(tmpl)
