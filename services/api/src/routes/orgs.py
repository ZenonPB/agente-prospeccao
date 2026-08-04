from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List

from src.db.dependencies import get_db
from src.db.models import (
    User,
    Organization,
    OrganizationMember,
    OrganizationRole,
    SalesRole,
)
from src.auth.dependencies import (
    get_current_user,
    get_user_organization,
    get_user_membership,
    require_org_admin,
    require_manager,
)
router = APIRouter(prefix="/orgs", tags=["orgs"])


class PatchMemberSalesRoleRequest(BaseModel):
    sales_role: SalesRole = Field(...)


def _member_dict(m: OrganizationMember) -> dict:
    return {
        "organization_id": str(m.organization_id),
        "user_id": str(m.user_id),
        "name": m.user.name if m.user else None,
        "email": m.user.email if m.user else None,
        "role": m.role.value if m.role else None,
        "sales_role": m.sales_role.value if m.sales_role else None,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.get("/me")
def get_my_org(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retorna a organização do usuário autenticado + seu papel de venda.

    O frontend precisa do `organization_id` e do `sales_role` do usuário
    atual para: (a) montar a tela de membros; (b) decidir se pode gerenciar
    papéis; (c) exibir o badge de papel de venda. Rota declarada antes de
    `/{org_id}/...` para não colidir com o path matching.
    """
    member = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == user.id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Usuário sem organização")

    return {
        "organization": {
            "id": str(member.organization_id),
            "name": member.organization.name if member.organization else None,
            "slug": member.organization.slug if member.organization else None,
        },
        "membership": {
            "role": member.role.value if member.role else None,
            "sales_role": member.sales_role.value if member.sales_role else None,
            "user_id": str(member.user_id),
        },
    }


@router.get("/my-organizations")
def list_my_organizations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lista todas as organizações das quais o usuário é membro.
    
    Usado pelo org switcher. Retorna lista com org + role + sales_role de
    cada membership. A org ativa é determinada pelo frontend (localStorage).
    """
    memberships = db.query(OrganizationMember).filter(
        OrganizationMember.user_id == user.id,
    ).order_by(OrganizationMember.created_at.asc()).all()
    
    return {
        "organizations": [
            {
                "id": str(m.organization_id),
                "name": m.organization.name if m.organization else None,
                "slug": m.organization.slug if m.organization else None,
                "role": m.role.value if m.role else None,
                "sales_role": m.sales_role.value if m.sales_role else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in memberships
        ]
    }


@router.get("/{org_id}/members")
def list_members(
    org_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_manager()),
):
    """Lista membros da organização (MANAGER/owner/admin).

    Owner/admin passam pelo require_manager (MANAGER é o papel de venda);
    o check do papel administrativo é complementar em `require_org_admin`
    usado no PATCH.
    """
    if str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    members = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org_id,
    ).order_by(OrganizationMember.created_at.asc()).all()
    return {"members": [_member_dict(m) for m in members]}


@router.patch("/{org_id}/members/{user_id}")
def patch_member_sales_role(
    org_id: str,
    user_id: str,
    body: PatchMemberSalesRoleRequest,
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_org_admin),
):
    """Define o papel de venda (CONSULTOR/ANALYST/MANAGER) de um membro.

    Item 2.1.4: apenas owner/admin da organização. O `sales_role` é POR
    organização — não vaza entre workspaces.
    """
    if str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    target = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == user_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Membro não encontrado")

    # Owner não pode ser rebaixado de papel administrativo (mantém seu OWNER).
    if target.user_id == actor.user_id and body.sales_role != target.sales_role:
        # Permitido, mas preserva ownership.
        pass

    target.sales_role = body.sales_role
    db.commit()
    db.refresh(target)
    return _member_dict(target)
