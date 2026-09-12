"""Monitoramento contínuo de sinais comerciais, sempre opt-in e quota-aware."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.db.models import Lead, Organization, Person, ProviderExecutionMetric
from src.services.data_intelligence_service import DataIntelligenceService
from services.email_verification_service import EmailVerificationService
from services.provider_execution_metric_service import ProviderExecutionMetricService
from services.prospecting.contact_verifier import ContactVerifier
from services.prospecting.employment_history_service import EmploymentHistoryService
from services.prospecting.external_intent_feed_provider import ExternalIntentFeedProvider
from services.quota_service import QuotaService

logger = logging.getLogger(__name__)


_PROVIDER_CONFIG = (
    ("job_postings", "JOB_INTENT_HTTP", "JOB_INTENT_URL", "JOB_INTENT_TOKEN"),
    ("company_news", "NEWS_INTENT_HTTP", "NEWS_INTENT_URL", "NEWS_INTENT_TOKEN"),
    ("social", "SOCIAL_INTENT_HTTP", "SOCIAL_INTENT_URL", "SOCIAL_INTENT_TOKEN"),
)


def _evidence_key(item: dict[str, Any]) -> tuple[str, str]:
    source = str(item.get("source") or "unknown").casefold()
    identity = item.get("external_id") or item.get("url") or item.get("title") or item.get("description") or ""
    return source, str(identity).strip().casefold()[:1000]


class ContinuousIntelligenceService:
    """Executa um ciclo por workspace sem ultrapassar opt-ins/cotas."""

    def __init__(self, db: Session):
        self.db = db
        self.metrics = ProviderExecutionMetricService()

    @staticmethod
    def _quota_enabled(org: Organization, key: str) -> bool:
        quotas = org.api_quota if isinstance(org.api_quota, dict) else {}
        try:
            return int(quotas.get(key) or 0) > 0
        except (TypeError, ValueError):
            return False

    def _is_due(self, org: Organization, *, force: bool) -> bool:
        if force:
            return True
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=settings.CONTINUOUS_INTELLIGENCE_MIN_INTERVAL_HOURS
        )
        latest = (
            self.db.query(ProviderExecutionMetric.recorded_at)
            .filter(
                ProviderExecutionMetric.organization_id == org.id,
                ProviderExecutionMetric.provider == "continuous_intelligence",
            )
            .order_by(ProviderExecutionMetric.recorded_at.desc())
            .first()
        )
        return not latest or not latest[0] or latest[0] < cutoff

    @staticmethod
    def _payload(lead: Lead, person: Person | None) -> dict[str, Any]:
        return {
            "company": {
                "name": lead.company_name,
                "domain": lead.normalized_domain,
                "website": lead.website,
                "city": lead.city,
                "state": lead.state,
                "linkedin_url": lead.company_linkedin_url,
                "instagram_url": lead.instagram_url,
            },
            "person": (
                {
                    "name": person.name,
                    "role": person.role_label,
                    "linkedin_url": person.linkedin_url,
                }
                if person else None
            ),
        }

    def _record_metric(
        self,
        org: Organization,
        provider: str,
        status: str,
        *,
        result_count: int = 0,
        duration_ms: int = 0,
        error_code: str | None = None,
        retryable: bool = False,
    ) -> None:
        self.metrics.record(
            self.db,
            org.id,
            provider,
            status,
            result_count=result_count,
            duration_ms=duration_ms,
            budget_used=1 if status not in {"disabled", "quota_exceeded"} else 0,
            error_code=error_code,
            retryable=retryable,
        )

    async def _collect_provider(
        self,
        org: Organization,
        lead: Lead,
        person: Person | None,
        *,
        provider_name: str,
        quota_key: str,
        endpoint: str,
        token: str,
    ) -> list[dict[str, Any]]:
        if not endpoint or not self._quota_enabled(org, quota_key):
            return []
        if not QuotaService.can_consume(self.db, str(org.id), quota_key):
            self._record_metric(org, provider_name, "quota_exceeded", error_code="daily_quota")
            return []

        provider = ExternalIntentFeedProvider(
            name=provider_name,
            endpoint=endpoint,
            token=token,
            max_retries=settings.INTENT_PROVIDER_MAX_RETRIES,
        )
        started = time.perf_counter()
        result = await provider.collect(self._payload(lead, person))
        duration_ms = int((time.perf_counter() - started) * 1000)
        QuotaService.consume(self.db, str(org.id), quota_key)
        self._record_metric(
            org,
            provider_name,
            result.status,
            result_count=len(result.evidence),
            duration_ms=duration_ms,
            error_code=result.error_code,
            retryable=result.retryable,
        )
        return list(result.evidence)

    async def _verify_email_if_enabled(self, org: Organization, person: Person | None) -> bool:
        if not person or not person.email:
            return False
        quota_key = "EMAIL_CATCHALL_PROBE"
        if not settings.EMAIL_CATCHALL_PROBE_ENABLED or not self._quota_enabled(org, quota_key):
            return False
        if not QuotaService.can_consume(self.db, str(org.id), quota_key):
            self._record_metric(org, "email_catchall", "quota_exceeded", error_code="daily_quota")
            return False

        started = time.perf_counter()
        verifier = ContactVerifier(
            EmailVerificationService(), enable_catchall_probe=True,
        )
        result = await verifier.verify_email(person)
        QuotaService.consume(self.db, str(org.id), quota_key)
        status = result.get("verification_status") or "unknown"
        self._record_metric(
            org,
            "email_catchall",
            "success" if status in {"deliverable", "catch_all", "domain_validated"} else "empty",
            result_count=1,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        person.email_verified = bool(result.get("email_verified"))
        person.verification_status = str(status)
        person.last_verified_at = datetime.now(timezone.utc)
        if person.email_verified:
            person.email_verified_at = person.last_verified_at
        self.db.add(person)
        return True

    async def run_once_for_org(self, org: Organization, *, force: bool = False) -> dict[str, Any]:
        if not self._quota_enabled(org, "CONTINUOUS_INTELLIGENCE"):
            return {"organization_id": str(org.id), "status": "disabled", "processed": 0, "changed": 0}
        if not self._is_due(org, force=force):
            return {"organization_id": str(org.id), "status": "not_due", "processed": 0, "changed": 0}
        if not QuotaService.can_consume(self.db, str(org.id), "CONTINUOUS_INTELLIGENCE"):
            return {"organization_id": str(org.id), "status": "quota_exceeded", "processed": 0, "changed": 0}

        leads = (
            self.db.query(Lead)
            .filter(Lead.organization_id == org.id, Lead.opt_out.is_(False))
            .order_by(Lead.next_action_at.asc().nullslast(), Lead.updated_at.desc().nullslast(), Lead.created_at.desc())
            .limit(settings.CONTINUOUS_INTELLIGENCE_BATCH_SIZE)
            .all()
        )
        person_ids = [lead.primary_person_id for lead in leads if lead.primary_person_id]
        people: dict[Any, Person] = {}
        if person_ids:
            people = {
                row.id: row
                for row in self.db.query(Person)
                .filter(Person.organization_id == org.id, Person.id.in_(person_ids))
                .all()
            }

        processed = 0
        changed = 0
        for lead in leads:
            person = people.get(lead.primary_person_id)
            existing = [item for item in (lead.evidence or []) if isinstance(item, dict)] if isinstance(lead.evidence, list) else []
            known = {_evidence_key(item) for item in existing}
            new_evidence: list[dict[str, Any]] = []

            for provider_name, quota_key, url_setting, token_setting in _PROVIDER_CONFIG:
                values = await self._collect_provider(
                    org,
                    lead,
                    person,
                    provider_name=provider_name,
                    quota_key=quota_key,
                    endpoint=str(getattr(settings, url_setting, "") or ""),
                    token=str(getattr(settings, token_setting, "") or ""),
                )
                for item in values:
                    key = _evidence_key(item)
                    if key in known:
                        continue
                    known.add(key)
                    new_evidence.append(item)
                    employment = item.get("employment")
                    if provider_name == "job_postings" and person and isinstance(employment, dict):
                        employment_payload = {
                            **employment,
                            "source": provider_name,
                            "observed_at": item.get("observed_at"),
                            "confidence": item.get("confidence"),
                            "source_reliability": item.get("source_reliability"),
                            "evidence_url": item.get("url"),
                        }
                        employment_result = EmploymentHistoryService.observe(person, employment_payload)
                        if employment_result["changed"]:
                            change_evidence = EmploymentHistoryService.latest_change_evidence(person)
                            if change_evidence and _evidence_key(change_evidence) not in known:
                                known.add(_evidence_key(change_evidence))
                                new_evidence.append(change_evidence)
                        self.db.add(person)

            email_updated = await self._verify_email_if_enabled(org, person)
            if new_evidence:
                lead.evidence = (existing + deepcopy(new_evidence))[-200:]
                timestamps = dict(lead.enrichment_timestamps or {})
                now_iso = datetime.now(timezone.utc).isoformat()
                sources = {str(item.get("source") or "") for item in new_evidence}
                if "job_postings" in sources or "employment_change" in sources:
                    timestamps["jobs"] = now_iso
                if sources & {"job_postings", "company_news", "social", "employment_change"}:
                    timestamps["intent"] = now_iso
                lead.enrichment_timestamps = timestamps
                self.db.add(lead)
                self.db.flush()
                DataIntelligenceService(self.db, org.id).analyze_lead(lead, persist=True)
                changed += 1
            elif email_updated:
                self.db.commit()
            processed += 1

        QuotaService.consume(self.db, str(org.id), "CONTINUOUS_INTELLIGENCE")
        self._record_metric(org, "continuous_intelligence", "success", result_count=changed)
        self.db.commit()
        return {
            "organization_id": str(org.id),
            "status": "success",
            "processed": processed,
            "changed": changed,
        }

    async def run_due_organizations(self) -> list[dict[str, Any]]:
        orgs = self.db.query(Organization).order_by(Organization.created_at.asc()).all()
        results: list[dict[str, Any]] = []
        for org in orgs:
            if not self._quota_enabled(org, "CONTINUOUS_INTELLIGENCE"):
                continue
            try:
                results.append(await self.run_once_for_org(org))
            except Exception as exc:  # noqa: BLE001
                self.db.rollback()
                logger.error("Inteligência contínua falhou na org %s: %s", org.id, exc)
                results.append({"organization_id": str(org.id), "status": "failed", "error": type(exc).__name__})
        return results
