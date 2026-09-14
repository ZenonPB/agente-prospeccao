"""Bloco D — UAT multi-workspace, production readiness e campanhas controladas.

Este módulo não cria uma fonte de verdade paralela: Campaign, Lead,
LeadOpportunity e CommercialOutcome continuam canônicos. Ele apenas agrega
readiness e mede cohorts existentes. Live outreach é fail-closed e exige
autorização humana explícita + provider opt-in; dry-run nunca envia mensagens.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.db.models import Campaign, CommercialOutcomeRow, Lead, LeadOpportunityRow


OFFER_RELEASE_MATRIX: tuple[dict[str, str], ...] = (
    {"offer_key": "landing_page", "label": "Landing pages", "hypothesis": "dor digital/conversão observável"},
    {"offer_key": "web_systems_erp", "label": "Sistemas sob medida", "hypothesis": "processo manual/fragmentado observável"},
    {"offer_key": "mechanical_engineering", "label": "Engenharia mecânica", "hypothesis": "projeto, expansão ou necessidade técnica observável"},
    {"offer_key": "trophies_sports", "label": "Troféus esportivos", "hypothesis": "evento esportivo com demanda de premiação"},
    {"offer_key": "trophies_mej", "label": "Troféus para MEJ", "hypothesis": "evento MEJ com organização e janela de compra identificáveis"},
)

LIVE_MODES = frozenset({"LIVE_AUTHORIZED"})
DRY_MODES = frozenset({"DRY_RUN", "REHEARSAL"})
_WON = frozenset({"WON", "CONVERTED", "SALE", "CLOSED_WON"})
_MEETING = frozenset({"MEETING", "MEETING_SCHEDULED", "MEETING_HELD"})
_REPLY = frozenset({"REPLY", "RESPONDED", "POSITIVE_REPLY"})


@dataclass(frozen=True)
class CampaignReleaseRequest:
    campaign_id: UUID
    mode: str = "DRY_RUN"
    provider_opt_in: bool = False
    authorized_by: UUID | None = None
    authorization_note: str | None = None
    cost_cap_brl: float | None = None
    max_contacts: int = 30

    def validate(self) -> None:
        mode = self.mode.upper().strip()
        if mode not in LIVE_MODES | DRY_MODES:
            raise ValueError("mode deve ser DRY_RUN, REHEARSAL ou LIVE_AUTHORIZED")
        if not 1 <= self.max_contacts <= 500:
            raise ValueError("max_contacts deve ficar entre 1 e 500")
        if self.cost_cap_brl is not None and self.cost_cap_brl < 0:
            raise ValueError("cost_cap_brl não pode ser negativo")
        if mode in LIVE_MODES:
            if not self.provider_opt_in:
                raise ValueError("live outreach exige provider opt-in explícito")
            if self.authorized_by is None:
                raise ValueError("live outreach exige autorização humana identificável")
            if not (self.authorization_note or "").strip():
                raise ValueError("live outreach exige justificativa/escopo da autorização")
            if self.cost_cap_brl is None:
                raise ValueError("live outreach exige teto de custo explícito")

    def public_manifest(self) -> dict[str, Any]:
        self.validate()
        data = asdict(self)
        data["campaign_id"] = str(self.campaign_id)
        data["authorized_by"] = str(self.authorized_by) if self.authorized_by else None
        data["mode"] = self.mode.upper().strip()
        data["can_send_external"] = data["mode"] in LIVE_MODES
        data["generated_at"] = datetime.now(timezone.utc).isoformat()
        return data


class BlockDService:
    """Agrega evidências de release sem duplicar entidades comerciais."""

    def __init__(self, db: Session, organization_id: UUID):
        self.db = db
        self.organization_id = organization_id

    def readiness(self) -> dict[str, Any]:
        """Readiness verificável: DB + invariantes de escopo e release.

        Não retorna segredo, DSN, token ou credencial. Provider externo é
        deliberadamente reportado como uma capacidade que ainda exige opt-in.
        """
        self.db.execute(text("SELECT 1"))
        orphan_campaigns = self.db.query(Campaign).filter(Campaign.organization_id.is_(None)).count()
        orphan_leads = self.db.query(Lead).filter(Lead.organization_id.is_(None)).count()
        return {
            "status": "READY" if orphan_campaigns == 0 and orphan_leads == 0 else "BLOCKED",
            "database": "READY",
            "tenant_integrity": {
                "orphan_campaigns": orphan_campaigns,
                "orphan_leads": orphan_leads,
                "ready": orphan_campaigns == 0 and orphan_leads == 0,
            },
            "external_providers": "OPT_IN_REQUIRED",
            "live_outreach": "HUMAN_AUTHORIZATION_REQUIRED",
            "backup_restore": "CI_REHEARSED",
            "as_of": datetime.now(timezone.utc).isoformat(),
        }

    def release_manifest(self, request: CampaignReleaseRequest) -> dict[str, Any]:
        request.validate()
        campaign = self.db.query(Campaign).filter(
            Campaign.id == request.campaign_id,
            Campaign.organization_id == self.organization_id,
        ).first()
        if campaign is None:
            raise ValueError("Campanha não encontrada neste workspace")
        offer_key = getattr(campaign, "offer_profile_key", None)
        supported = {row["offer_key"] for row in OFFER_RELEASE_MATRIX}
        if offer_key not in supported:
            raise ValueError("Campanha precisa estar vinculada a uma oferta suportada pelo release D3")
        result = request.public_manifest()
        result.update({
            "organization_id": str(self.organization_id),
            "offer_key": offer_key,
            "campaign_name": campaign.name,
            "guardrails": [
                "tenant scoped",
                "provider opt-in antes de live",
                "quota/custo antes da chamada externa",
                "outcome atribuído à oportunidade/oferta/versão",
                "nenhuma publicação automática de learning",
            ],
        })
        return result

    def campaign_funnel(self, campaign_id: UUID) -> dict[str, Any]:
        campaign = self.db.query(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.organization_id == self.organization_id,
        ).first()
        if campaign is None:
            raise ValueError("Campanha não encontrada neste workspace")

        leads = self.db.query(Lead).filter(
            Lead.organization_id == self.organization_id,
            Lead.campaign_id == campaign_id,
        ).all()
        lead_ids = [row.id for row in leads]
        opportunities = []
        outcomes = []
        if lead_ids:
            opportunities = self.db.query(LeadOpportunityRow).filter(
                LeadOpportunityRow.organization_id == self.organization_id,
                LeadOpportunityRow.lead_id.in_(lead_ids),
            ).all()
            outcomes = self.db.query(CommercialOutcomeRow).filter(
                CommercialOutcomeRow.organization_id == self.organization_id,
                CommercialOutcomeRow.lead_id.in_(lead_ids),
            ).all()

        buckets_by_lead: dict[str, set[str]] = {}
        for outcome in outcomes:
            key = str(outcome.lead_id)
            buckets_by_lead.setdefault(key, set()).add(str(getattr(outcome.outcome, "value", outcome.outcome)).upper())

        replied = meetings = won = 0
        revenue = 0.0
        attributed = 0
        for outcome in outcomes:
            value = str(getattr(outcome.outcome, "value", outcome.outcome)).upper()
            attributed += int(outcome.lead_opportunity_id is not None)
            if value in _WON:
                revenue += float(outcome.value or 0)
        for values in buckets_by_lead.values():
            is_won = bool(values & _WON)
            is_meeting = is_won or bool(values & _MEETING)
            is_reply = is_meeting or bool(values & _REPLY)
            replied += int(is_reply)
            meetings += int(is_meeting)
            won += int(is_won)

        total = len(leads)
        return {
            "campaign_id": str(campaign_id),
            "organization_id": str(self.organization_id),
            "offer_key": getattr(campaign, "offer_profile_key", None),
            "leads": total,
            "opportunities": len(opportunities),
            "replied": replied,
            "meetings": meetings,
            "won": won,
            "revenue": round(revenue, 2),
            "reply_rate": round(replied / total, 4) if total else None,
            "meeting_rate": round(meetings / total, 4) if total else None,
            "win_rate": round(won / total, 4) if total else None,
            "outcomes": len(outcomes),
            "attributed_outcomes": attributed,
            "attribution_rate": round(attributed / len(outcomes), 4) if outcomes else None,
            "calibration_ready": total >= 30 and won >= 3 and bool(outcomes) and attributed / len(outcomes) >= 0.8,
            "claim": "observational",
            "as_of": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def release_matrix() -> list[dict[str, str]]:
        return [dict(row) for row in OFFER_RELEASE_MATRIX]
