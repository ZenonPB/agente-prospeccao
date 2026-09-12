"""Leitura de Data Health e priorização de refresh por workspace."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import Company, EmailSuppression, Enrichment, Lead, LeadOpportunityRow, Person, ProviderExecutionMetric
from services.prospecting.freshness_policy import evaluate_freshness
from services.prospecting.phone_verification_service import verify_phone


class DataHealthService:
    def __init__(self, db: Session, organization_id: Any):
        self.db = db
        self.organization_id = organization_id

    def _lead_freshness(self, lead: Lead, enrichment: Enrichment | None, person: Person | None) -> list[dict[str, Any]]:
        timestamps = lead.enrichment_timestamps if isinstance(lead.enrichment_timestamps, dict) else {}
        return [
            evaluate_freshness("website", timestamps.get("site") or (enrichment.updated_at if enrichment else None)),
            evaluate_freshness("company_registry", timestamps.get("business") or timestamps.get("registry")),
            evaluate_freshness("technographics", timestamps.get("technographics") or timestamps.get("site")),
            evaluate_freshness("intent", timestamps.get("intent")),
            evaluate_freshness("jobs", timestamps.get("jobs")),
            evaluate_freshness("email", person.last_verified_at if person and person.email else None),
            evaluate_freshness("phone", person.last_verified_at if person and person.phone else None),
            evaluate_freshness("employment", person.last_verified_at if person else None),
        ]

    def _provider_health(self, *, now: datetime) -> list[dict[str, Any]]:
        """Agrega estados recentes sem carregar métricas individuais em memória."""
        since = now - timedelta(days=7)
        rows = (
            self.db.query(
                ProviderExecutionMetric.provider,
                ProviderExecutionMetric.status,
                func.count(ProviderExecutionMetric.id),
                func.max(ProviderExecutionMetric.recorded_at),
            )
            .filter(
                ProviderExecutionMetric.organization_id == self.organization_id,
                ProviderExecutionMetric.recorded_at >= since,
            )
            .group_by(ProviderExecutionMetric.provider, ProviderExecutionMetric.status)
            .all()
        )
        by_provider: dict[str, dict[str, Any]] = {}
        for provider, status, count, last_seen in rows:
            bucket = by_provider.setdefault(
                str(provider),
                {"provider": str(provider), "statuses": {}, "total": 0, "failures": 0, "last_seen_at": None},
            )
            bucket["statuses"][str(status)] = int(count)
            bucket["total"] += int(count)
            if str(status) in {"failed", "timeout", "quota_exceeded"}:
                bucket["failures"] += int(count)
            if last_seen and (bucket["last_seen_at"] is None or last_seen.isoformat() > bucket["last_seen_at"]):
                bucket["last_seen_at"] = last_seen.isoformat()
        for bucket in by_provider.values():
            bucket["failure_rate"] = round(bucket["failures"] / bucket["total"] * 100.0, 1) if bucket["total"] else 0.0
            if bucket["statuses"].get("quota_exceeded"):
                bucket["health"] = "quota_exceeded"
            elif bucket["failures"]:
                bucket["health"] = "degraded"
            elif bucket["statuses"].get("disabled") and len(bucket["statuses"]) == 1:
                bucket["health"] = "disabled"
            else:
                bucket["health"] = "healthy"
        return sorted(by_provider.values(), key=lambda item: (-item["failure_rate"], item["provider"]))

    def overview(self, *, limit: int = 100) -> dict[str, Any]:
        leads = (
            self.db.query(Lead)
            .filter(Lead.organization_id == self.organization_id)
            .order_by(Lead.updated_at.desc().nullslast(), Lead.created_at.desc())
            .limit(min(max(limit, 1), 500))
            .all()
        )
        lead_ids = [lead.id for lead in leads]
        company_ids = [lead.company_id for lead in leads if lead.company_id]
        person_ids = [lead.primary_person_id for lead in leads if lead.primary_person_id]

        enrichments = {}
        if lead_ids:
            rows = self.db.query(Enrichment).filter(Enrichment.lead_id.in_(lead_ids)).all()
            for row in rows:
                enrichments.setdefault(row.lead_id, row)
        persons = {}
        if person_ids:
            rows = self.db.query(Person).filter(Person.organization_id == self.organization_id, Person.id.in_(person_ids)).all()
            persons = {row.id: row for row in rows}
        companies = {}
        if company_ids:
            rows = self.db.query(Company).filter(Company.organization_id == self.organization_id, Company.id.in_(company_ids)).all()
            companies = {row.id: row for row in rows}

        opportunity_counts = Counter()
        if lead_ids:
            rows = self.db.query(LeadOpportunityRow.lead_id).filter(
                LeadOpportunityRow.organization_id == self.organization_id,
                LeadOpportunityRow.lead_id.in_(lead_ids),
            ).all()
            opportunity_counts.update(row[0] for row in rows)

        emails = {
            email.lower()
            for email in (
                [person.email for person in persons.values() if person.email]
                + [lead.email for lead in leads if lead.email]
            )
        }
        suppressed_emails = set()
        if emails:
            rows = self.db.query(EmailSuppression.email).filter(
                EmailSuppression.organization_id == self.organization_id,
                EmailSuppression.email.in_(emails),
            ).all()
            suppressed_emails = {str(row[0]).lower() for row in rows}

        items: list[dict[str, Any]] = []
        counters: Counter[str] = Counter()
        now = datetime.now(timezone.utc)
        for lead in leads:
            person = persons.get(lead.primary_person_id)
            company = companies.get(lead.company_id)
            freshness = self._lead_freshness(lead, enrichments.get(lead.id), person)
            stale_keys = [item["key"] for item in freshness if item["state"] == "stale"]
            unknown_keys = [item["key"] for item in freshness if item["state"] == "unknown"]
            contact_email = (person.email if person and person.email else lead.email)
            contact_phone = (person.phone if person and person.phone else (lead.phone or lead.whatsapp))
            phone = verify_phone(contact_phone)
            email_invalid = bool(contact_email and contact_email.lower() in suppressed_emails)
            missing_decision_maker = person is None
            duplicate_risk = not bool(lead.cnpj or lead.normalized_domain or lead.place_id)
            missing_phone = not bool(contact_phone)
            missing_email = not bool(contact_email)

            if stale_keys:
                counters["stale"] += 1
            if email_invalid:
                counters["invalid_email"] += 1
            if missing_phone:
                counters["missing_phone"] += 1
            if missing_email:
                counters["missing_email"] += 1
            if missing_decision_maker:
                counters["missing_decision_maker"] += 1
            if duplicate_risk:
                counters["identity_risk"] += 1

            priority = 0
            priority += 35 if opportunity_counts[lead.id] else 0
            priority += 25 if lead.next_action_at and lead.next_action_at <= now else 0
            priority += min(30, len(stale_keys) * 6)
            priority += min(20, len(unknown_keys) * 2)
            priority += 15 if missing_decision_maker else 0
            priority += 10 if email_invalid else 0

            items.append({
                "lead_id": str(lead.id),
                "company_name": lead.company_name,
                "company_id": str(company.id) if company else None,
                "person_id": str(person.id) if person else None,
                "freshness": freshness,
                "stale_keys": stale_keys,
                "unknown_keys": unknown_keys,
                "phone_verification": phone,
                "email_invalid": email_invalid,
                "missing_email": missing_email,
                "missing_phone": missing_phone,
                "missing_decision_maker": missing_decision_maker,
                "identity_risk": duplicate_risk,
                "opportunity_count": opportunity_counts[lead.id],
                "refresh_priority": priority,
            })

        items.sort(key=lambda item: (-item["refresh_priority"], item["company_name"].lower()))
        total = len(items)
        healthy = sum(
            1 for item in items
            if not item["stale_keys"] and not item["email_invalid"] and not item["missing_decision_maker"] and not item["identity_risk"]
        )
        return {
            "total": total,
            "healthy": healthy,
            "health_rate": round((healthy / total * 100.0), 1) if total else 100.0,
            "issues": dict(counters),
            "provider_health": self._provider_health(now=now),
            "items": items,
            "generated_at": now.isoformat(),
        }

    def refresh_candidates(self, *, limit: int = 25) -> list[dict[str, Any]]:
        overview = self.overview(limit=max(limit * 4, 100))
        return [item for item in overview["items"] if item["refresh_priority"] > 0][:limit]
