"""Agregação org-scoped de outcomes para diagnósticos de piloto.

A consulta é estritamente read-only. Outcomes sem vínculo com lead permanecem
fora da amostra da campanha e nunca são atribuídos por heurística.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.db.models import CommercialOutcomeRow, Lead

_REPLY = {"REPLY", "RESPONDED", "POSITIVE_REPLY"}
_MEETING = {"MEETING", "MEETING_SCHEDULED", "MEETING_HELD"}
_WON = {"WON", "CONVERTED", "SALE", "CLOSED_WON"}


def summarize_campaign_outcomes(
    db: Session,
    organization_id: Any,
    *,
    campaign_id: Any | None = None,
) -> dict[str, Any]:
    """Resume outcomes observados sem cruzar tenants nem inventar atribuição."""
    lead_query = db.query(Lead.id).filter(Lead.organization_id == organization_id)
    if campaign_id is not None:
        lead_query = lead_query.filter(Lead.campaign_id == campaign_id)
    lead_ids = [row[0] for row in lead_query.all()]

    if not lead_ids:
        return _empty()

    rows = db.query(CommercialOutcomeRow).filter(
        CommercialOutcomeRow.organization_id == organization_id,
        CommercialOutcomeRow.lead_id.in_(lead_ids),
    ).all()

    attributed = 0
    replies = 0
    meetings = 0
    wins = 0
    revenue = 0.0
    for row in rows:
        if row.lead_opportunity_id is not None:
            attributed += 1
        value = str(row.outcome or "").strip().upper()
        if value in _WON:
            wins += 1
            meetings += 1
            replies += 1
            revenue += float(row.value or 0)
        elif value in _MEETING:
            meetings += 1
            replies += 1
        elif value in _REPLY:
            replies += 1

    total = len(rows)
    return {
        "total": total,
        "attributed": attributed,
        "unattributed": total - attributed,
        "attribution_rate": round(attributed / total, 4) if total else None,
        "replies": replies,
        "meetings": meetings,
        "wins": wins,
        "revenue": round(revenue, 2),
    }


def _empty() -> dict[str, Any]:
    return {
        "total": 0,
        "attributed": 0,
        "unattributed": 0,
        "attribution_rate": None,
        "replies": 0,
        "meetings": 0,
        "wins": 0,
        "revenue": 0.0,
    }
