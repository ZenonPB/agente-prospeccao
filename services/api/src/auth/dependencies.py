"""Dependência FastAPI para autenticação JWT e isolamento por organização."""
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.db.dependencies import get_db
from src.db.models import User, Organization, OrganizationMember, OrganizationRole, SalesRole
from src.auth.security import decode_access_token
from src.services.org_service import user_organization

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer(auto_error=False)

# Peso de cada papel de venda (maior = mais privilégio de leitura/gestão).
SALES_ROLE_WEIGHT = {
    SalesRole.CONSULTOR: 0,
    SalesRole.ANALYST: 1,
    SalesRole.MANAGER: 2,
}


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Valida o token JWT e retorna o usuário atual."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação não fornecido",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token malformado",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
        )

    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Como get_current_user, mas retorna None em vez de 401 se não houver token."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    return db.query(User).filter(User.id == user_id).first()


def get_user_organization(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Organization:
    """Resolve a organização ativa do usuário autenticado.

    Usada como dependência nas rotas para isolar os dados por workspace.
    Levanta 403 se o usuário não pertence a nenhuma organização.
    """
    org = user_organization(db, user)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem organização vinculada",
        )
    return org


def get_user_membership(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationMember:
    """Resolve o membership do usuário na organização ativa.

    Centraliza o acesso ao `sales_role` (papel de venda) e ao `role`
    (owner/admin/member) do usuário na org. Levanta 403 se não for membro.
    """
    member = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == user.id,
    ).first()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário não é membro de uma organização",
        )
    return member


def require_sales_role(min_role: SalesRole = SalesRole.ANALYST):
    """Fábrica de dependência: exige um papel de venda mínimo (por peso).

    Uso:
        membership: OrganizationMember = Depends(require_sales_role(SalesRole.ANALYST))

    - CONSULTOR  (peso 0) — operação (funil próprio).
    - ANALYST    (peso 1) — leitura total + BI.
    - MANAGER    (peso 2) — leitura total + BI + gestão de papéis.
    """
    min_weight = SALES_ROLE_WEIGHT[min_role]

    def _dep(
        member: OrganizationMember = Depends(get_user_membership),
    ) -> OrganizationMember:
        # Owner/admin da org têm privilégio administrativo: equivalem a MANAGER
        # (leitura total + BI) independente do papel de venda atribuído.
        if member.role in (OrganizationRole.OWNER, OrganizationRole.ADMIN):
            weight = SALES_ROLE_WEIGHT[SalesRole.MANAGER]
        else:
            weight = SALES_ROLE_WEIGHT.get(member.sales_role, 0)
        if weight < min_weight:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Papel de venda insuficiente para esta ação",
            )
        return member

    return _dep


def require_analyst() -> OrganizationMember:
    """Dependency: ANALYST ou MANAGER (leitura total + BI).

    Uso: `member = Depends(require_analyst())`.
    """
    return require_sales_role(SalesRole.ANALYST)


def require_manager() -> OrganizationMember:
    """Dependency: apenas MANAGER (gestão de papéis).

    Uso: `member = Depends(require_manager())`.
    """
    return require_sales_role(SalesRole.MANAGER)


def require_org_admin(
    member: OrganizationMember = Depends(get_user_membership),
) -> OrganizationMember:
    """Dependency: owner ou admin da organização (gestão de membros)."""
    if member.role not in (OrganizationRole.OWNER, OrganizationRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas owner/admin da organização podem executar esta ação",
        )
    return member
