"""API de Vertentes: leitura tenant-safe da estratégia comercial efetiva."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.dependencies import get_user_organization, require_analyst
from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember
from src.services.vertente_service import VertenteService

router = APIRouter(prefix="/vertentes", tags=["vertentes"])


@router.get("")
def list_vertentes(
    db: Session = Depends(get_db),
    org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(require_analyst()),
):
    items = VertenteService(db, org.id).list()
    return {"items": items, "total": len(items)}


@router.get("/{offer_key}")
def get_vertente(
    offer_key: str,
    db: Session = Depends(get_db),
    org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(require_analyst()),
):
    item = VertenteService(db, org.id).get(offer_key)
    if item is None:
        raise HTTPException(status_code=404, detail="Vertente não encontrada")
    return item
