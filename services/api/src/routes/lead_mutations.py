"""Mutações críticas de lead com invariantes comerciais centralizadas.

O módulo existe para retirar as operações de maior risco do router monolítico de
``leads.py`` sem quebrar os imports públicos atuais. ``install_lead_mutations``
substitui somente as quatro operações listadas abaixo no ``leads.router`` e
mantém todo o restante do contrato intacto.

As garantias são deliberadamente redundantes com o banco: validação de request,
serviço de domínio e constraints/índices. Assim uma corrida, um cliente antigo ou
um caminho alternativo não consegue violar o fato comercial persistido.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.dependencies import (
    get_current_user,
    get_user_membership,
    get_user_organization,
)
from src.db.dependencies import get_db
from src.db.models import (
    Conversion,
    Lead,
    LeadStatus,
    LostReason,
    Organization,
    OrganizationMember,
    User,
)
from src.middleware.rate_limit import limiter
from src.services.lead_status_service import transition_lead_status

logger = logging.getLogger(__name__)

_CONVERSION_CONFLICT = "Este lead já tem uma conversão registrada para esta oferta"


class UpdateLeadStatusRequest(BaseModel):
    status: LeadStatus
    lost_reason: Optional[LostReason] = None

    @model_validator(mode="after")
    def validate_commercial_outcome(self):
        if self.status == LeadStatus.PERDIDO and self.lost_reason is None:
            raise ValueError("Informe o motivo da perda")
        # Motivo de perda não tem semântica fora de PERDIDO. Ignorá-lo em vez de
        # persistir evita colapsar DESQUALIFICADO e LOST em dados históricos.
        if self.status != LeadStatus.PERDIDO:
            self.lost_reason = None
        return self


class MarkLostRequest(BaseModel):
    lost_reason: LostReason = Field(..., description="Motivo da perda (obrigatório)")


class MarkDisqualifiedRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)


def find_duplicate_conversion(db, lead_id, offer_key, lead_opportunity_id=None):
    """Usa exatamente a mesma chave lógica do índice único do banco.

    ``lead_opportunity_id`` é mantido na assinatura por compatibilidade, porém
    não estreita a unicidade: uma venda é única por lead + oferta.
    """
    del lead_opportunity_id
    normalized_offer = offer_key or "unknown"
    return (
        db.query(Conversion)
        .filter(
            Conversion.lead_id == lead_id,
            func.coalesce(Conversion.offer_key, "unknown") == normalized_offer,
        )
        .order_by(Conversion.converted_at.desc())
        .first()
    )


def install_lead_mutations(leads_module) -> None:
    """Instala os endpoints endurecidos no router público de leads.

    A composição fica no pacote ``src.routes`` para preservar ``leads.router``
    como contrato de import usado por testes e pela aplicação enquanto o router
    monolítico é migrado gradualmente.
    """
    router = leads_module.router

    original_register_conversion = leads_module.register_conversion

    def _can_access(member: OrganizationMember, lead: Lead) -> bool:
        return leads_module._can_access_lead(member, lead)

    def _record_outcome(db: Session, lead: Lead, outcome: str, event_key: str) -> None:
        leads_module._record_commercial_outcome(
            db,
            lead,
            outcome,
            event_key=event_key,
        )

    def update_lead_status(
        lead_id: str,
        body: UpdateLeadStatusRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
        _org: Organization = Depends(get_user_organization),
        member: OrganizationMember = Depends(get_user_membership),
    ):
        lead = db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.organization_id == _org.id,
        ).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead não encontrado")
        if not _can_access(member, lead):
            raise HTTPException(status_code=403, detail="Acesso negado a este lead")

        previous = lead.status
        activity = transition_lead_status(
            db,
            lead,
            body.status,
            user_id=str(user.id) if user else None,
            lost_reason=body.lost_reason,
        )

        outcome_by_status = {
            LeadStatus.RESPONDIDO: "RESPONDED",
            LeadStatus.REUNIAO_MARCADA: "MEETING",
            LeadStatus.REUNIAO_FEITA: "MEETING",
            LeadStatus.PERDIDO: "LOST",
        }
        outcome = outcome_by_status.get(body.status)
        if outcome:
            _record_outcome(
                db,
                lead,
                outcome,
                event_key=f"activity:{getattr(activity, 'id', None)}",
            )

        db.commit()
        db.refresh(lead)

        from src.services.webhook_outbound_service import enqueue_webhook
        enqueue_webhook(
            background_tasks,
            db,
            lead.organization_id,
            event="lead.status_changed",
            data={
                "lead_id": str(lead.id),
                "company_name": lead.company_name,
                "previous_status": previous.value if previous else None,
                "status": lead.status.value,
                "lost_reason": lead.lost_reason.value if lead.lost_reason else None,
                "changed_by": str(user.id) if user else None,
            },
        )

        suggested = leads_module._suggest_next_action_at(body.status)
        return {
            "id": str(lead.id),
            "company_name": lead.company_name,
            "status": lead.status.value,
            "suggested_next_action_at": suggested.isoformat() if suggested else None,
        }

    @limiter.limit("60/minute")
    async def mark_lead_lost(
        request: Request,
        lead_id: str,
        body: MarkLostRequest,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
        _org: Organization = Depends(get_user_organization),
        member: OrganizationMember = Depends(get_user_membership),
    ):
        lead = db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.organization_id == _org.id,
        ).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead não encontrado")
        if not _can_access(member, lead):
            raise HTTPException(status_code=403, detail="Acesso negado a este lead")

        transition_lead_status(
            db,
            lead,
            LeadStatus.PERDIDO,
            user_id=str(user.id) if user else None,
            lost_reason=body.lost_reason,
        )
        _record_outcome(db, lead, "LOST", event_key=f"mark-lost:{lead.id}")
        db.commit()
        return {"status": lead.status.value, "lost_reason": lead.lost_reason.value}

    @limiter.limit("60/minute")
    async def mark_lead_disqualified(
        request: Request,
        lead_id: str,
        body: MarkDisqualifiedRequest,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
        _org: Organization = Depends(get_user_organization),
        member: OrganizationMember = Depends(get_user_membership),
    ):
        lead = db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.organization_id == _org.id,
        ).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead não encontrado")
        if not _can_access(member, lead):
            raise HTTPException(status_code=403, detail="Acesso negado a este lead")

        transition_lead_status(
            db,
            lead,
            LeadStatus.DESQUALIFICADO,
            user_id=str(user.id) if user else None,
            disqualification_reason=body.reason,
        )
        db.commit()
        return {"status": lead.status.value}

    def register_conversion(
        lead_id: str,
        body,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
        _org: Organization = Depends(get_user_organization),
        member: OrganizationMember = Depends(get_user_membership),
    ):
        try:
            return original_register_conversion(
                lead_id,
                body,
                background_tasks,
                db,
                user,
                _org,
                member,
            )
        except IntegrityError:
            # Corrida entre check e insert é esperada sob concorrência. A
            # constraint do banco decide; a API traduz para conflito de domínio.
            db.rollback()
            logger.info(
                "Conversão duplicada recusada por constraint",
                extra={"lead_id": str(lead_id)},
            )
            raise HTTPException(status_code=409, detail=_CONVERSION_CONFLICT)

    # A função acima é criada dinamicamente porque o schema original vive no
    # router legado. Antes de registrar o endpoint, devolvemos a anotação real
    # do body para o FastAPI construir exatamente o mesmo contrato OpenAPI.
    register_conversion.__annotations__["body"] = leads_module.RegisterConversionRequest

    # Funções públicas continuam importáveis pelo nome antigo. Isso preserva os
    # testes e consumidores internos que chamam diretamente a função de rota.
    leads_module.UpdateLeadStatusRequest = UpdateLeadStatusRequest
    leads_module.MarkLostRequest = MarkLostRequest
    leads_module.MarkDisqualifiedRequest = MarkDisqualifiedRequest
    leads_module.find_duplicate_conversion = find_duplicate_conversion
    leads_module.update_lead_status = update_lead_status
    leads_module.mark_lead_lost = mark_lead_lost
    leads_module.mark_lead_disqualified = mark_lead_disqualified
    leads_module.register_conversion = register_conversion

    replacements = {
        ("/{lead_id}/status", "PATCH"): update_lead_status,
        ("/{lead_id}/mark-lost", "POST"): mark_lead_lost,
        ("/{lead_id}/mark-disqualified", "POST"): mark_lead_disqualified,
        ("/{lead_id}/conversion", "POST"): register_conversion,
    }

    # Remover os APIRoutes antigos evita rotas duplicadas no runtime e no
    # OpenAPI. Em seguida os contratos endurecidos entram no mesmo router.
    router.routes[:] = [
        route
        for route in router.routes
        if not any(
            route.path == path and method in (route.methods or set())
            for (path, method) in replacements
        )
    ]

    router.add_api_route(
        "/{lead_id}/status",
        update_lead_status,
        methods=["PATCH"],
        name="update_lead_status",
    )
    router.add_api_route(
        "/{lead_id}/mark-lost",
        mark_lead_lost,
        methods=["POST"],
        name="mark_lead_lost",
    )
    router.add_api_route(
        "/{lead_id}/mark-disqualified",
        mark_lead_disqualified,
        methods=["POST"],
        name="mark_lead_disqualified",
    )
    router.add_api_route(
        "/{lead_id}/conversion",
        register_conversion,
        methods=["POST"],
        name="register_conversion",
    )
