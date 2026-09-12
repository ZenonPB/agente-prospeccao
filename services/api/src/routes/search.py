"""Busca avançada de empresas/pessoas e interpretação de intenção de busca."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, get_user_organization
from src.db.dependencies import get_db
from src.db.models import Organization, User
from src.middleware.rate_limit import limiter
from src.schemas.search import (
    CompanySearchRequest,
    NaturalLanguageSearchRequest,
    PeopleSearchRequest,
    SearchIntent,
)
from src.services.prospect_search_service import ProspectSearchService

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/companies")
@limiter.limit("60/minute")
def search_companies(
    request: Request,
    body: CompanySearchRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
):
    """Busca empresas já conhecidas no workspace, sem chamar providers."""
    try:
        return ProspectSearchService(db, org.id).search_companies(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/people")
@limiter.limit("60/minute")
def search_people(
    request: Request,
    body: PeopleSearchRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
):
    """Busca pessoas canônicas do workspace e calcula acionabilidade."""
    return ProspectSearchService(db, org.id).search_people(body)


@router.post("/interpret", response_model=SearchIntent)
@limiter.limit("15/minute")
async def interpret_search(
    request: Request,
    body: NaturalLanguageSearchRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    org: Organization = Depends(get_user_organization),
):
    """Traduz linguagem natural em SearchIntent validado; não executa busca."""
    from services.secret_service import SecretService
    from services.search_intent_service import SearchIntentInterpreter

    keys = await SecretService.resolve_all(db, str(org.id))
    api_key = keys.get("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="IA de interpretação indisponível. Configure a chave Groq do workspace.",
        )

    raw = await SearchIntentInterpreter(api_key).interpret(
        body.query,
        target=body.target,
        db=db,
        organization_id=str(org.id),
    )
    if raw is None:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível interpretar a busca agora. Use os filtros manuais ou tente novamente.",
        )
    try:
        intent = SearchIntent.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="A interpretação retornou filtros inválidos. Refine o pedido ou use os filtros manuais.",
        ) from exc

    if body.target != "auto" and intent.target != body.target:
        raise HTTPException(
            status_code=502,
            detail="A interpretação não respeitou o tipo de busca solicitado.",
        )
    return intent
