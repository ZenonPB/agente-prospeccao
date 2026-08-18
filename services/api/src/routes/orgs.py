from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
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
    SalesTarget,
    OrgAuditEvent,
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
from src.services.org_service import create_organization, unassign_user_leads_in_org  # noqa: E402
from src.services.org_audit_service import log_org_event, list_org_audit  # noqa: E402

router = APIRouter(prefix="/orgs", tags=["orgs"])


class PatchMemberSalesRoleRequest(BaseModel):
    sales_role: SalesRole = Field(...)


class CreateOrgRequest(BaseModel):
    """Cria um novo workspace."""
    name: str = Field(..., min_length=2, max_length=255)
    email_from: Optional[str] = Field(None, max_length=255)


class RenameOrgRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)


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
            # Throttling & remetente dedicado: expõe o teto diário,
            # a janela de espalhamento e quantos envios já foram hoje.
            "daily_email_limit": member.organization.daily_email_limit if member.organization else None,
            "send_window_start": member.organization.send_window_start if member.organization else None,
            "send_window_end": member.organization.send_window_end if member.organization else None,
            "sends_today": sends_today(db, member.organization_id)[0] if member.organization else 0,
            "email_from": member.organization.email_from if member.organization else None,
            # SLA de leads parados (dias).
            "sla_qualified_no_contact_days": member.organization.sla_qualified_no_contact_days if member.organization else None,
            "sla_responded_no_next_action_days": member.organization.sla_responded_no_next_action_days if member.organization else None,
            "sla_opened_no_response_days": member.organization.sla_opened_no_response_days if member.organization else None,
            "qualification_threshold": member.organization.qualification_threshold if member.organization else None,
            "webhook_url": member.organization.webhook_url if member.organization else None,
            "webhook_configured": bool(member.organization.webhook_url) if member.organization else False,
            "scheduling_url": member.organization.scheduling_url if member.organization else None,
        },
        "membership": {
            "role": member.role.name if member.role else None,
            "sales_role": member.sales_role.value if member.sales_role else None,
            "user_id": str(member.user_id),
        },
    }


@router.post("")
def create_org(
    body: CreateOrgRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cria uma nova organização.

    O usuário logado vira OWNER (sales_role MANAGER). Slugs são derivados do
    nome e tornados únicos automaticamente.
    """
    org = create_organization(db, name=body.name, owner_user=user, email_from=body.email_from)
    log_org_event(db, org.id, OrgAuditEvent.ORG_CREATED, actor=user, target_type="org", detail=org.name)
    db.commit()
    db.refresh(org)
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "email_from": org.email_from,
        "role": "OWNER",
        "sales_role": "MANAGER",
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
    _user: Organization = Depends(get_user_organization),
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
    actor: OrganizationMember = Depends(require_manager()),
):
    """Define o papel de venda (CONSULTOR/ANALYST/MANAGER) de um membro.

    Gestores (MANAGER) e owner/admin. O `sales_role` é POR organização —
    não vaza entre workspaces. Remoção/transferência de membros permanece
    owner/admin-only.
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

    detail = f"{target.sales_role.value if target.sales_role else '-'} -> {body.sales_role.value}"
    target.sales_role = body.sales_role
    log_org_event(
        db, org_id, OrgAuditEvent.MEMBER_ROLE_CHANGED, actor=actor,
        target_type="member", target_id=user_id, detail=f"sales_role: {detail}",
    )
    db.commit()
    db.refresh(target)
    return _member_dict(target)


class TransferOwnerRequest(BaseModel):
    new_owner_user_id: str = Field(..., min_length=1)


@router.delete("/{org_id}/members/{user_id}")
def remove_member(
    org_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_org_admin),
):
    """Remove um membro da organização e desatribui seus leads.

    - Owner não pode ser removido (deve transferir ownership antes).
    - Admins não podem remover a si mesmos por este endpoint (usam /leave).
    - Admins não-owner não podem remover outros admins.
    """
    import uuid
    if str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    target = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == user_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Membro não encontrado")

    if target.role == OrganizationRole.OWNER:
        raise HTTPException(
            status_code=400,
            detail="O proprietário da organização não pode ser removido. Transfira a propriedade antes.",
        )
    if str(target.user_id) == str(actor.user_id):
        raise HTTPException(
            status_code=400,
            detail="Para sair da organização, utilize a opção 'Sair da organização'.",
        )
    if actor.role != OrganizationRole.OWNER and target.role == OrganizationRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Administradores não podem remover outros administradores.",
        )

    unassign_user_leads_in_org(
        db,
        org_id=uuid.UUID(org_id),
        user_id=uuid.UUID(user_id),
        actor_user_id=actor.user_id,
        reason="Membro desvinculado da organização por um administrador",
    )
    log_org_event(
        db, org_id, OrgAuditEvent.MEMBER_REMOVED, actor=actor,
        target_type="member", target_id=user_id, detail=target.user.email if target.user else None,
    )
    db.delete(target)
    db.commit()
    return {"removed": True, "user_id": user_id, "org_id": org_id}


@router.post("/{org_id}/transfer-owner")
def transfer_org_ownership(
    org_id: str,
    body: TransferOwnerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Transfere a propriedade (OWNER) da organização para outro membro."""
    import uuid
    actor = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == user.id,
    ).first()
    if not actor or actor.role != OrganizationRole.OWNER:
        raise HTTPException(
            status_code=403,
            detail="Apenas o proprietário da organização pode transferir a propriedade.",
        )

    if str(actor.user_id) == body.new_owner_user_id:
        raise HTTPException(status_code=400, detail="Você já é o proprietário desta organização.")

    target = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == body.new_owner_user_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Novo proprietário deve ser membro ativo da organização.")

    actor.role = OrganizationRole.ADMIN
    target.role = OrganizationRole.OWNER
    target.sales_role = SalesRole.MANAGER
    log_org_event(
        db, org_id, OrgAuditEvent.OWNER_TRANSFERRED, actor=actor,
        target_type="member", target_id=body.new_owner_user_id,
        detail=f"novo owner: {target.user.email if target.user else ''}",
    )
    db.commit()
    return {
        "transferred": True,
        "previous_owner_id": str(actor.user_id),
        "new_owner_id": str(target.user_id),
    }


@router.post("/{org_id}/leave")
def leave_org(
    org_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Permite que um membro saia da organização."""
    import uuid
    member = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == org_id,
        OrganizationMember.user_id == user.id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Você não é membro desta organização.")

    if member.role == OrganizationRole.OWNER:
        raise HTTPException(
            status_code=400,
            detail="O proprietário não pode sair da organização sem antes transferir a propriedade.",
        )

    unassign_user_leads_in_org(
        db,
        org_id=uuid.UUID(org_id),
        user_id=user.id,
        actor_user_id=user.id,
        reason="Membro saiu espontaneamente da organização",
    )
    log_org_event(db, org_id, OrgAuditEvent.MEMBER_LEFT, actor=user, target_type="member", target_id=str(user.id))
    db.delete(member)
    db.commit()
    return {"left": True, "org_id": org_id, "user_id": str(user.id)}


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

    Retorna apenas quais `key_name` estão definidas, para a UI
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
    log_org_event(
        db, org_id, OrgAuditEvent.SECRET_SET, actor=actor,
        target_type="secret", target_id=normalized,
    )
    db.commit()
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
    log_org_event(
        db, org_id, OrgAuditEvent.SECRET_DELETED, actor=actor,
        target_type="secret", target_id=normalized,
    )
    db.commit()
    return {"key_name": normalized, "configured": False}


class PatchOrgSettingsRequest(BaseModel):
    auto_send_email: Optional[bool] = None
    # Throttling: teto diário e janela de espalhamento (HH:MM).
    daily_email_limit: Optional[int] = None
    send_window_start: Optional[str] = None
    send_window_end: Optional[str] = None
    email_from: Optional[str] = None
    # SLA de leads parados (dias).
    sla_qualified_no_contact_days: Optional[int] = None
    sla_responded_no_next_action_days: Optional[int] = None
    sla_opened_no_response_days: Optional[int] = None
    # Limiar QUALIFICADO/DESQUALIFICADO aplicado pelo orquestrador (1-100).
    qualification_threshold: Optional[int] = None
    # Webhook genérico de saída (eventos da org).
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    # Link de agendamento (Cal.com/Calendly) injetado no outreach.
    scheduling_url: Optional[str] = None
    # Teto diário por provedor (BYOK vs pool). Ex.: {"GROQ_API_KEY": 500}.
    api_quota: Optional[Dict[str, int]] = None


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
    """Atualiza configurações da organização.

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
    if body.sla_qualified_no_contact_days is not None:
        if not 1 <= body.sla_qualified_no_contact_days <= 120:
            raise HTTPException(status_code=400, detail="sla_qualified_no_contact_days deve estar entre 1 e 120")
        org.sla_qualified_no_contact_days = body.sla_qualified_no_contact_days
    if body.sla_responded_no_next_action_days is not None:
        if not 1 <= body.sla_responded_no_next_action_days <= 120:
            raise HTTPException(status_code=400, detail="sla_responded_no_next_action_days deve estar entre 1 e 120")
        org.sla_responded_no_next_action_days = body.sla_responded_no_next_action_days
    if body.sla_opened_no_response_days is not None:
        if not 1 <= body.sla_opened_no_response_days <= 120:
            raise HTTPException(status_code=400, detail="sla_opened_no_response_days deve estar entre 1 e 120")
        org.sla_opened_no_response_days = body.sla_opened_no_response_days
    if body.qualification_threshold is not None:
        if not 1 <= body.qualification_threshold <= 100:
            raise HTTPException(status_code=400, detail="qualification_threshold deve estar entre 1 e 100")
        org.qualification_threshold = body.qualification_threshold
    if body.webhook_url is not None:
        value = body.webhook_url.strip()
        if value and not (value.startswith("http://") or value.startswith("https://")):
            raise HTTPException(status_code=400, detail="webhook_url deve começar com http:// ou https://")
        org.webhook_url = value or None
    if body.webhook_secret is not None:
        org.webhook_secret = body.webhook_secret.strip() or None
    if body.scheduling_url is not None:
        value = body.scheduling_url.strip()
        if value and not (value.startswith("http://") or value.startswith("https://")):
            raise HTTPException(status_code=400, detail="scheduling_url deve começar com http:// ou https://")
        org.scheduling_url = value or None
    if body.api_quota is not None:
        from services.secret_service import KEY_NAMES
        valid_keys = set(KEY_NAMES)
        for key, value in body.api_quota.items():
            if key not in valid_keys:
                raise HTTPException(status_code=400, detail=f"key de cota inválida: {key}")
            if not 1 <= int(value) <= 1_000_000:
                raise HTTPException(status_code=400, detail=f"limite inválido para {key}")
        org.api_quota = dict(body.api_quota)

    changed = body.model_dump(exclude_unset=True, exclude_none=True)
    if changed:
        log_org_event(
            db, org_id, OrgAuditEvent.ORG_SETTINGS_UPDATED, actor=actor,
            target_type="org", detail=", ".join(sorted(changed.keys())),
        )
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
        "sla_qualified_no_contact_days": org.sla_qualified_no_contact_days,
        "sla_responded_no_next_action_days": org.sla_responded_no_next_action_days,
        "sla_opened_no_response_days": org.sla_opened_no_response_days,
        "qualification_threshold": org.qualification_threshold,
        "webhook_url": org.webhook_url,
        "webhook_configured": bool(org.webhook_url),
        "scheduling_url": org.scheduling_url,
    }


@router.patch("/{org_id}/name")
def rename_org(
    org_id: str,
    body: RenameOrgRequest,
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_org_admin),
):
    """Renomeia a organização (owner/admin)."""
    if str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    org.name = body.name.strip()
    log_org_event(
        db, org_id, OrgAuditEvent.ORG_RENAMED, actor=actor,
        target_type="org", detail=org.name,
    )
    db.commit()
    db.refresh(org)
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
    }


class UpsertSalesTargetRequest(BaseModel):
    """Meta mensal de vendas para um consultor."""
    user_id: str = Field(..., min_length=1)
    month: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    meetings_target: int = Field(0, ge=0, le=1000)
    revenue_target: float = Field(0.0, ge=0)


def _sales_target_dict(t: SalesTarget) -> dict:
    return {
        "id": str(t.id),
        "user_id": str(t.user_id),
        "name": t.user.name if t.user else None,
        "email": t.user.email if t.user else None,
        "month": t.month,
        "meetings_target": t.meetings_target or 0,
        "revenue_target": float(t.revenue_target or 0),
    }


@router.get("/{org_id}/sales-targets")
def list_sales_targets(
    org_id: str,
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"),
    db: Session = Depends(get_db),
    _user: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_manager()),
):
    """Lista as metas de vendas da organização.

    MANAGER/ANALYST/owner/admin podem consultar. Se `month` for omitido,
    retorna o mês atual (YYYY-MM).
    """
    if str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    import datetime
    target_month = month or datetime.date.today().strftime("%Y-%m")
    targets = (
        db.query(SalesTarget)
        .filter(
            SalesTarget.organization_id == org_id,
            SalesTarget.month == target_month,
        )
        .all()
    )
    return {"month": target_month, "targets": [_sales_target_dict(t) for t in targets]}


@router.put("/{org_id}/sales-targets")
def upsert_sales_target(
    org_id: str,
    body: UpsertSalesTargetRequest,
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_org_admin),
):
    """Cria/atualiza a meta mensal de um consultor.

    Upsert por `(organization_id, user_id, month)`. Owner/admin apenas.
    """
    if str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    target = (
        db.query(SalesTarget)
        .filter(
            SalesTarget.organization_id == org_id,
            SalesTarget.user_id == body.user_id,
            SalesTarget.month == body.month,
        )
        .first()
    )
    if target:
        target.meetings_target = body.meetings_target
        target.revenue_target = body.revenue_target
    else:
        target = SalesTarget(
            organization_id=org_id,
            user_id=body.user_id,
            month=body.month,
            meetings_target=body.meetings_target,
            revenue_target=body.revenue_target,
        )
        db.add(target)
    log_org_event(
        db, org_id, OrgAuditEvent.SALES_TARGET_UPSERTED, actor=actor,
        target_type="target", target_id=str(target.user_id), detail=f"{body.month}",
    )
    db.commit()
    db.refresh(target)
    return _sales_target_dict(target)


@router.delete("/{org_id}/sales-targets/{target_id}")
def delete_sales_target(
    org_id: str,
    target_id: str,
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_org_admin),
):
    """Remove uma meta mensal de vendas. Owner/admin."""
    if str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    target = db.query(SalesTarget).filter(
        SalesTarget.id == target_id,
        SalesTarget.organization_id == org_id,
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Meta não encontrada")

    db.delete(target)
    log_org_event(
        db, org_id, OrgAuditEvent.SALES_TARGET_DELETED, actor=actor,
        target_type="target", target_id=target_id, detail=target.month,
    )
    db.commit()
    return {"deleted": True, "target_id": target_id}


@router.get("/{org_id}/usage")
def get_org_usage(
    org_id: str,
    db: Session = Depends(get_db),
    _org: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_manager()),
):
    """Medidor de cotas diárias da org por provedor.

    Retorna o uso de hoje por `key_name` (usado/limite/restante/%) e o flag
    `alert` quando qualquer provedor passou de 80% do teto. MANAGER+/owner/admin.
    """
    from services.quota_service import QuotaService

    if str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    usage = QuotaService.usage_for_org(db, org_id)
    alert = any(u["pct"] >= 80 for u in usage)
    return {"usage": usage, "alert": alert}


@router.get("/{org_id}/audit-log")
def list_org_audit_log(
    org_id: str,
    event: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: Organization = Depends(get_user_organization),
    actor: OrganizationMember = Depends(require_manager()),
):
    """Lista a auditoria de eventos administrativos da org (MANAGER/owner/admin).

    Filtra por `event` (valor do enum) e ordena do mais recente para o mais
    antigo. Não expõe valores de secret — apenas `key_name` no target_id.
    """
    if str(actor.organization_id) != org_id:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    entries = list_org_audit(
        db, org_id, event=OrgAuditEvent(event) if event else None, limit=limit,
    )

    return {
        "entries": [
            {
                "id": str(e.id),
                "event": e.event.value,
                "actor_id": str(e.actor_id) if e.actor_id else None,
                "actor_name": e.actor_name,
                "actor_email": e.actor_email,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "detail": e.detail,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ]
    }
