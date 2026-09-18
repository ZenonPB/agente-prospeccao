"""Métricas comerciais atribuídas a oportunidades reais.

Não existe fallback silencioso para a oportunidade de maior score: outcomes sem
`lead_opportunity_id` permanecem sem atribuição e são reportados separadamente.
Isso evita ensinar o sistema com uma causalidade inventada.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import CommercialOutcomeRow, Company, Lead, LeadOpportunityRow, Person, ProviderExecutionMetric
from services.prospecting.pilot_metrics import evaluate_pilot_readiness, summarize_pilot


POSITIVE_REPLY = {"REPLY", "RESPONDED", "POSITIVE_REPLY"}
MEETING = {"MEETING", "MEETING_SCHEDULED", "MEETING_HELD"}
WON = {"WON", "CONVERTED", "SALE", "CLOSED_WON"}


def _outcome_bucket(value: str | None) -> str:
    normalized = str(value or "").strip().upper()
    if normalized in WON:
        return "won"
    if normalized in MEETING:
        return "meeting"
    if normalized in POSITIVE_REPLY:
        return "reply"
    return "other"


def _signals(row: LeadOpportunityRow) -> set[str]:
    raw = row.signals_matched
    if isinstance(raw, list):
        values: set[str] = set()
        for item in raw:
            if isinstance(item, str):
                values.add(item)
            elif isinstance(item, dict):
                key = item.get("key") or item.get("signal") or item.get("name")
                if key:
                    values.add(str(key))
        return values
    if isinstance(raw, dict):
        return {str(key) for key, value in raw.items() if value not in (False, None, 0, "")}
    return set()


class CommercialIntelligenceService:
    def __init__(self, db: Session, organization_id: Any):
        self.db = db
        self.organization_id = organization_id

    def attribution_health(self) -> dict[str, Any]:
        rows = self.db.query(CommercialOutcomeRow).filter(
            CommercialOutcomeRow.organization_id == self.organization_id,
        ).all()
        attributed = sum(1 for row in rows if row.lead_opportunity_id is not None)
        total = len(rows)
        return {
            "total_outcomes": total,
            "attributed_outcomes": attributed,
            "unattributed_outcomes": total - attributed,
            "attribution_rate": round(attributed / total, 4) if total else None,
        }

    def signal_effectiveness(self, *, min_sample: int = 3) -> list[dict[str, Any]]:
        opportunities = self.db.query(LeadOpportunityRow).filter(
            LeadOpportunityRow.organization_id == self.organization_id,
        ).all()
        outcomes = self.db.query(CommercialOutcomeRow).filter(
            CommercialOutcomeRow.organization_id == self.organization_id,
            CommercialOutcomeRow.lead_opportunity_id.isnot(None),
        ).all()
        by_opportunity: dict[str, list[CommercialOutcomeRow]] = defaultdict(list)
        for outcome in outcomes:
            by_opportunity[str(outcome.lead_opportunity_id)].append(outcome)

        stats: dict[str, dict[str, float]] = defaultdict(lambda: {
            "sample": 0.0, "reply": 0.0, "meeting": 0.0, "won": 0.0, "revenue": 0.0,
        })
        for opportunity in opportunities:
            signals = _signals(opportunity)
            if not signals:
                continue
            related = by_opportunity.get(str(opportunity.id), [])
            buckets = {_outcome_bucket(row.outcome) for row in related}
            revenue = sum(float(row.value or 0) for row in related if _outcome_bucket(row.outcome) == "won")
            for signal in signals:
                item = stats[signal]
                item["sample"] += 1
                item["reply"] += float(bool(buckets & {"reply", "meeting", "won"}))
                item["meeting"] += float(bool(buckets & {"meeting", "won"}))
                item["won"] += float("won" in buckets)
                item["revenue"] += revenue

        result: list[dict[str, Any]] = []
        for signal, item in stats.items():
            sample = int(item["sample"])
            if sample < min_sample:
                continue
            result.append({
                "signal": signal,
                "sample_size": sample,
                "reply_rate": round(item["reply"] / sample, 4),
                "meeting_rate": round(item["meeting"] / sample, 4),
                "win_rate": round(item["won"] / sample, 4),
                "revenue_per_signal": round(item["revenue"] / sample, 2),
            })
        result.sort(key=lambda row: (row["win_rate"], row["meeting_rate"], row["sample_size"]), reverse=True)
        return result

    def provider_effectiveness(self) -> list[dict[str, Any]]:
        metrics = self.db.query(ProviderExecutionMetric).filter(
            ProviderExecutionMetric.organization_id == self.organization_id,
        ).all()
        outcomes = self.db.query(CommercialOutcomeRow).filter(
            CommercialOutcomeRow.organization_id == self.organization_id,
            CommercialOutcomeRow.lead_opportunity_id.isnot(None),
        ).all()

        by_provider: dict[str, dict[str, float]] = defaultdict(lambda: {
            "requests": 0.0, "candidates": 0.0, "cost": 0.0, "replies": 0.0,
            "meetings": 0.0, "wins": 0.0, "revenue": 0.0,
        })
        for metric in metrics:
            provider = str(metric.provider or "unknown")
            item = by_provider[provider]
            item["requests"] += 1
            item["candidates"] += max(0, int(metric.result_count or 0))
            item["cost"] += float(metric.cost or 0)
        for outcome in outcomes:
            provider = str(outcome.provider or "unknown")
            bucket = _outcome_bucket(outcome.outcome)
            item = by_provider[provider]
            if bucket in {"reply", "meeting", "won"}:
                item["replies"] += 1
            if bucket in {"meeting", "won"}:
                item["meetings"] += 1
            if bucket == "won":
                item["wins"] += 1
                item["revenue"] += float(outcome.value or 0)

        result: list[dict[str, Any]] = []
        for provider, item in by_provider.items():
            cost = item["cost"]
            revenue = item["revenue"]
            result.append({
                "provider": provider,
                "requests": int(item["requests"]),
                "candidates": int(item["candidates"]),
                "replies": int(item["replies"]),
                "meetings": int(item["meetings"]),
                "wins": int(item["wins"]),
                "cost": round(cost, 4),
                "revenue": round(revenue, 2),
                "roi": round((revenue - cost) / cost, 4) if cost > 0 else None,
            })
        result.sort(key=lambda row: (row["wins"], row["revenue"], row["candidates"]), reverse=True)
        return result

    def precision_at_k(self, *, k_reply: int = 10, k_meeting: int = 10, k_won: int = 25) -> dict[str, Any]:
        opportunities = self.db.query(LeadOpportunityRow).filter(
            LeadOpportunityRow.organization_id == self.organization_id,
        ).order_by(LeadOpportunityRow.score.desc(), LeadOpportunityRow.updated_at.desc()).all()
        outcome_rows = self.db.query(CommercialOutcomeRow).filter(
            CommercialOutcomeRow.organization_id == self.organization_id,
            CommercialOutcomeRow.lead_opportunity_id.isnot(None),
        ).all()
        buckets: dict[str, set[str]] = defaultdict(set)
        for row in outcome_rows:
            buckets[str(row.lead_opportunity_id)].add(_outcome_bucket(row.outcome))

        def ratio(top_k: int, accepted: set[str]) -> float | None:
            sample = opportunities[:top_k]
            if not sample:
                return None
            hits = sum(1 for row in sample if buckets.get(str(row.id), set()) & accepted)
            return round(hits / len(sample), 4)

        return {
            "reply_top_10": ratio(k_reply, {"reply", "meeting", "won"}),
            "meeting_top_10": ratio(k_meeting, {"meeting", "won"}),
            "won_top_25": ratio(k_won, {"won"}),
            "ranked_opportunities": len(opportunities),
        }

    def coverage(self) -> dict[str, Any]:
        companies = self.db.query(func.count(Company.id)).filter(Company.organization_id == self.organization_id).scalar() or 0
        leads = self.db.query(func.count(Lead.id)).filter(Lead.organization_id == self.organization_id).scalar() or 0
        icp = self.db.query(func.count(LeadOpportunityRow.id)).filter(
            LeadOpportunityRow.organization_id == self.organization_id,
            LeadOpportunityRow.score >= 60,
        ).scalar() or 0
        contactable = self.db.query(func.count(Person.id)).filter(
            Person.organization_id == self.organization_id,
            Person.routable.is_(True),
        ).scalar() or 0
        prospected_leads = self.db.query(func.count(func.distinct(CommercialOutcomeRow.lead_id))).filter(
            CommercialOutcomeRow.organization_id == self.organization_id,
        ).scalar() or 0
        won_leads = self.db.query(func.count(func.distinct(CommercialOutcomeRow.lead_id))).filter(
            CommercialOutcomeRow.organization_id == self.organization_id,
            func.upper(CommercialOutcomeRow.outcome).in_(tuple(WON)),
        ).scalar() or 0
        return {
            "known_companies": int(companies),
            "leads": int(leads),
            "icp_matches": int(icp),
            "contactable_people": int(contactable),
            "prospected_leads": int(prospected_leads),
            "won_leads": int(won_leads),
            "penetration_rate": round(won_leads / companies, 4) if companies else None,
            "market_universe": None,
            "market_universe_status": "unknown",
        }

    def niche_priors(self, *, min_sample: int = 5) -> list[dict[str, Any]]:
        leads = {str(row.id): row for row in self.db.query(Lead).filter(Lead.organization_id == self.organization_id).all()}
        opportunities = {str(row.id): row for row in self.db.query(LeadOpportunityRow).filter(LeadOpportunityRow.organization_id == self.organization_id).all()}
        outcomes = self.db.query(CommercialOutcomeRow).filter(
            CommercialOutcomeRow.organization_id == self.organization_id,
            CommercialOutcomeRow.lead_opportunity_id.isnot(None),
        ).all()
        stats: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: {"sample": 0.0, "wins": 0.0, "revenue": 0.0})
        seen: set[tuple[str, str, str]] = set()
        for outcome in outcomes:
            opportunity = opportunities.get(str(outcome.lead_opportunity_id))
            lead = leads.get(str(outcome.lead_id))
            if not opportunity or not lead:
                continue
            campaign = getattr(lead, "campaign", None)
            segment = str(getattr(campaign, "target_segment", None) or getattr(lead, "category", None) or "Não informado")
            key = (str(opportunity.offer_key), segment)
            entity_key = (key[0], key[1], str(opportunity.id))
            if entity_key not in seen:
                stats[key]["sample"] += 1
                seen.add(entity_key)
            if _outcome_bucket(outcome.outcome) == "won":
                stats[key]["wins"] += 1
                stats[key]["revenue"] += float(outcome.value or 0)
        rows = []
        for (offer, segment), item in stats.items():
            sample = int(item["sample"])
            if sample < min_sample:
                continue
            rows.append({
                "offer_key": offer,
                "segment": segment,
                "sample_size": sample,
                "win_rate": round(item["wins"] / sample, 4),
                "revenue": round(item["revenue"], 2),
            })
        rows.sort(key=lambda row: (row["win_rate"], row["revenue"], row["sample_size"]), reverse=True)
        return rows

    def pilot_readiness(self, *, campaign_id: Any | None = None) -> dict[str, Any]:
        """Mede um piloto sem alterar o ranking nem executar providers.

        Toda leitura é limitada à organização ativa; `campaign_id`, quando
        informado, é um filtro adicional e nunca substitui o filtro de tenant.
        O endpoint consome apenas telemetria e score_vector já persistidos.
        """
        lead_query = self.db.query(Lead).filter(Lead.organization_id == self.organization_id)
        metric_query = self.db.query(ProviderExecutionMetric).filter(
            ProviderExecutionMetric.organization_id == self.organization_id,
        )
        if campaign_id is not None:
            lead_query = lead_query.filter(Lead.campaign_id == campaign_id)
            metric_query = metric_query.filter(ProviderExecutionMetric.campaign_id == campaign_id)

        leads = lead_query.all()
        lead_ids = {row.id for row in leads}
        outcome_query = self.db.query(CommercialOutcomeRow).filter(
            CommercialOutcomeRow.organization_id == self.organization_id,
        )
        if campaign_id is not None:
            # CommercialOutcomeRow não possui campaign_id: o escopo da campanha
            # é derivado somente dos leads já filtrados e tenant-scoped.
            if lead_ids:
                outcome_query = outcome_query.filter(CommercialOutcomeRow.lead_id.in_(lead_ids))
            else:
                outcome_query = outcome_query.filter(CommercialOutcomeRow.id.is_(None))
        outcomes = outcome_query.all()
        person_ids = {row.primary_person_id for row in leads if row.primary_person_id is not None}
        routable_ids: set[str] = set()
        if person_ids:
            routable_ids = {
                str(row.id)
                for row in self.db.query(Person).filter(
                    Person.organization_id == self.organization_id,
                    Person.id.in_(person_ids),
                    Person.routable.is_(True),
                ).all()
            }

        projected_leads = []
        for lead in leads:
            vector = lead.score_vector if isinstance(lead.score_vector, dict) else {}
            dimensions = vector.get("commercial_dimensions")
            projected_leads.append({
                "legacy_score": float(lead.qualification_score) if lead.qualification_score is not None else None,
                "qualified": str(getattr(lead.status, "value", lead.status) or "").upper() == "QUALIFICADO",
                "contactable": bool(lead.primary_person_id and str(lead.primary_person_id) in routable_ids),
                "commercial_dimensions": dimensions if isinstance(dimensions, dict) else None,
            })

        projected_metrics = [
            {
                "status": row.status,
                "result_count": row.result_count,
                "cost": float(row.cost) if row.cost is not None else None,
            }
            for row in metric_query.all()
        ]
        projected_outcomes = [
            {
                "lead_id": str(row.lead_id),
                "outcome": row.outcome,
                # O modelo legado pode preencher lead_opportunity_id/snapshot por
                # heurística em record_for_lead(). Sem provenance explícita não
                # declaramos atribuição causal confiável para promover scoring.
                "attributed": False,
                "attribution_status": "unverified_legacy_link",
            }
            for row in outcomes
        ]
        summary = summarize_pilot(projected_leads, projected_metrics, projected_outcomes)
        return {
            "scope": {
                "organization_id": str(self.organization_id),
                "campaign_id": str(campaign_id) if campaign_id is not None else None,
            },
            "summary": summary,
            "readiness": evaluate_pilot_readiness(summary),
        }

    def dashboard(self) -> dict[str, Any]:
        return {
            "attribution": self.attribution_health(),
            "signal_effectiveness": self.signal_effectiveness(),
            "provider_effectiveness": self.provider_effectiveness(),
            "precision": self.precision_at_k(),
            "coverage": self.coverage(),
            "niche_priors": self.niche_priors(),
        }
