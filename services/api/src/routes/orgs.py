from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import sys

from src.db.dependencies import get_db
from src.db.models import (
    User,
    Organization,
    OrganizationMember,
    OrganizationRole,
    SalesRole,
    OrganizationSecret,
)
from src.auth.dependencies import (
    get_current_user,
    get_user_organization,
    get_user_membership,
    require_org_admin,
    require_manager,
)

_workers_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "workers", "src")
if _workers_path not in sys.path:
    sys.path.insert(0, _workers_path)
from services.secret_service import SecretService, KEY_NAMES  # noqa: E402
from src.services.cadence_service import sends_today  # noqa: E402

router = APIRouter(prefix="/orgs", tags=["orgs"])


class PatchMemberSalesRoleRequest(BaseModel):
    sales_role: SalesRole = Field(...)


def _member_dict(m: OrganizationMember) -> dict:
    return {
        "organization_id": str(m.organization_id),
        "user_id": str(m.user_id),
        "name": m.user.name if m.user else None,
        "email": m.user.email if m.user else None,
        # `.name` do enum (OWNER/ADMIN/MEMBER) — contrato da API é maiúsculo,
        # igual ao tipo `OrgRole` no frontend. O valor do enum no banco
        # continua minúsculo ("owner"/"admin"/"member").
        "role": m.role.name if m.role else None,
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
            "auto_send_email": bool(member.organization.auto_send_email) if member.organization else False,
            # Item 4.3 — throttling & remetente dedicado: expõe o teto diário,
            # a janela de espalhamento e quantos envios já foram hoje.
            "daily_email_limit": member.organization.daily_email_limit if member.organization else None,
            "send_window_start": member.organization.send_window_start if member.organization else None,
            "send_window_end": member.organization.send_window_end if member.organization else None,
            "sends_today": sends_today(db, member.organization_id)[0] if member.organization else 0,
            "email_from": member.organization.email_from if member.organization else None,
        },
        "membership": {
            "role": member.role.name if member.role else None,
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
                "role": m.role.name if m.role else None,
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


class PutSecretRequest(BaseModel):
    value: str = Field(..., min_length=1, description="Valor da chave de API")


@router.get("/{org_id}/secrets")
def list_org_secrets(
    org_id: str,
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_org_admin),
):
    """Lista as chaves BYOK configuradas pela organização (sem expor valores).

    Item 3.5: retorna apenas quais `key_name` estão definidas, para a UI
    marcar como "configurado" sem nunca exibir o segredo.
    """
    if str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    secrets = db.query(OrganizationSecret).filter(
        OrganizationSecret.organization_id == org_id,
    ).all()
    configured = {s.key_name for s in secrets}
    return {
        "secrets": [
            {"key_name": key, "configured": key in configured}
            for key in KEY_NAMES
        ]
    }


@router.put("/{org_id}/secrets/{key_name}")
async def put_org_secret(
    org_id: str,
    key_name: str,
    body: PutSecretRequest,
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_org_admin),
):
    """Grava (ou sobrescreve) uma chave BYOK da organização, criptografada.

    A partir de então, o pipeline e as rotas resolvem essa chave para a org
    em vez do pool global.
    """
    if str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    normalized = key_name.upper().strip()
    if normalized not in KEY_NAMES:
        raise HTTPException(status_code=400, detail=f"key_name inválido: {normalized}")

    await SecretService.set_org_secret(db, org_id, normalized, body.value)
    return {"key_name": normalized, "configured": True}


@router.delete("/{org_id}/secrets/{key_name}")
async def delete_org_secret(
    org_id: str,
    key_name: str,
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_org_admin),
):
    """Remove a chave BYOK da organização (volta a usar o pool global)."""
    if str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    normalized = key_name.upper().strip()
    if normalized not in KEY_NAMES:
        raise HTTPException(status_code=400, detail=f"key_name inválido: {normalized}")

    removed = await SecretService.delete_org_secret(db, org_id, normalized)
    if not removed:
        raise HTTPException(status_code=404, detail="Secret não configurado")
    return {"key_name": normalized, "configured": False}


class PatchOrgSettingsRequest(BaseModel):
    auto_send_email: Optional[bool] = None
    # Item 4.3 — throttling: teto diário e janela de espalhamento (HH:MM).
    daily_email_limit: Optional[int] = None
    send_window_start: Optional[str] = None
    send_window_end: Optional[str] = None
    email_from: Optional[str] = None


def _validate_hhmm(value: Optional[str]) -> None:
    """Valida formato "HH:MM" (00:00–23:59). None passa sem validação."""
    import re
    if value is None:
        return
    if not re.fullmatch(r"\d{2}:\d{2}", value):
        raise HTTPException(status_code=400, detail=f"valor de janela inválido: '{value}' (use HH:MM)")
    h, m = value.split(":")
    if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
        raise HTTPException(status_code=400, detail=f"valor de janela fora do intervalo: '{value}' (use HH:MM)")


@router.patch("/{org_id}")
def patch_org_settings(
    org_id: str,
    body: PatchOrgSettingsRequest,
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_org_admin),
):
    """Atualiza configurações da organização (item 3.7).

    `auto_send_email` liga/desliga o envio automático de follow-ups da cadência
    (default: humano-no-loop). Apenas owner/admin da org.
    """
    if str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    if body.auto_send_email is not None:
        org.auto_send_email = body.auto_send_email
    if body.daily_email_limit is not None:
        if body.daily_email_limit < 1 or body.daily_email_limit > 500:
            raise HTTPException(status_code=400, detail="daily_email_limit deve estar entre 1 e 500")
        org.daily_email_limit = body.daily_email_limit
    if body.send_window_start is not None:
        _validate_hhmm(body.send_window_start)
        org.send_window_start = body.send_window_start
    if body.send_window_end is not None:
        _validate_hhmm(body.send_window_end)
        org.send_window_end = body.send_window_end
    if body.email_from is not None:
        org.email_from = body.email_from or None
    db.commit()
    db.refresh(org)

    return {
        "id": str(org.id),
        "name": org.name,
        "auto_send_email": bool(org.auto_send_email),
        "daily_email_limit": org.daily_email_limit,
        "send_window_start": org.send_window_start,
        "send_window_end": org.send_window_end,
        "email_from": org.email_from,
        "sends_today": sends_today(db, org.id)[0],
    }
