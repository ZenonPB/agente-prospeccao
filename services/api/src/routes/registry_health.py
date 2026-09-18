"""Saúde da base de empresas: diagnóstico read-only do universo empresarial."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.auth.dependencies import get_user_organization, require_analyst
from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember
from src.services.registry_health_service import RegistryHealthService

router = APIRouter(prefix="/registry", tags=["registry"])


def _service(
    db: Session = Depends(get_db),
    _member: OrganizationMember = Depends(require_analyst()),
    _org: Organization = Depends(get_user_organization),
) -> RegistryHealthService:
    return RegistryHealthService(db)


@router.get("/health")
def health(service: RegistryHealthService = Depends(_service)):
    """Deriva estado de snapshots/ledger; nunca executa import/download."""
    return service.health()
