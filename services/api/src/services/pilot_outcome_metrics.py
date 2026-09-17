"""Agregação org-scoped de outcomes para diagnósticos de piloto.

A consulta é estritamente read-only. O funil é consolidado por lead para que
transições sucessivas de status não inflem replies, meetings ou wins.

`lead_opportunity_id` não é tratado como prova de atribuição explícita: o fluxo
legado pode preenchê-lo heuristicamente. Enquanto a provenance dessa decisão
não estiver persistida, o diagnóstico expõe apenas a quantidade de eventos
vinculados e mantém atribuição confiável como desconhecida.
"""
from __future__ import annotations

from collections import defaultdict
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
    if not rows:
        return _empty()

    buckets_by_lead: dict[str, set[str]] = defaultdict(set)
    won_values_by_lead: dict[str, list[float]] = defaultdict(list)
    linked_events = 0

    for row in rows:
        lead_key = str(row.lead_id)
        value = str(row.outcome or "").strip().upper()
        if row.lead_opportunity_id is not None:
            linked_events += 1
        if value in _WON:
            buckets_by_lead[lead_key].update(("reply", "meeting", "won"))
            won_values_by_lead[lead_key].append(float(row.value or 0))
        elif value in _MEETING:
            buckets_by_lead[lead_key].update(("reply", "meeting"))
        elif value in _REPLY:
            buckets_by_lead[lead_key].add("reply")
        else:
            # Preserva o lead na amostra de outcomes mesmo quando o evento não
            # pertence aos três estágios comerciais medidos.
            buckets_by_lead.setdefault(lead_key, set())

    replies = sum("reply" in buckets for buckets in buckets_by_lead.values())
    meetings = sum("meeting" in buckets for buckets in buckets_by_lead.values())
    wins = sum("won" in buckets for buckets in buckets_by_lead.values())
    # Um mesmo fechamento pode gerar mais de um evento de status. Para o
    # diagnóstico de funil, usa-se no máximo um valor de fechamento por lead.
    revenue = sum(max(values) for values in won_values_by_lead.values() if values)

    return {
        "leads_with_outcomes": len(buckets_by_lead),
        "outcome_events": len(rows),
        "linked_events": linked_events,
        "reliable_attribution_rate": None,
        "attribution_status": "unknown_without_explicit_provenance",
        "replies": replies,
        "meetings": meetings,
        "wins": wins,
        "revenue": round(revenue, 2),
    }


def _empty() -> dict[str, Any]:
    return {
        "leads_with_outcomes": 0,
        "outcome_events": 0,
        "linked_events": 0,
        "reliable_attribution_rate": None,
        "attribution_status": "unknown_without_explicit_provenance",
        "replies": 0,
        "meetings": 0,
        "wins": 0,
        "revenue": 0.0,
    }
