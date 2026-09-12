"""Monitoramento contínuo de sinais comerciais, sempre opt-in e quota-aware."""
from __future__ import annotations

import asyncio
import logging
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.db.models import Lead, Organization, Person, ProviderExecutionMetric
from src.services.data_intelligence_service import DataIntelligenceService
from services.email_verification_service import EmailVerificationService
from services.provider_execution_metric_service import ProviderExecutionMetricService
from services.prospecting.contact_verifier import ContactVerifier
from services.prospecting.employment_history_service import EmploymentHistoryService
from services.prospecting.external_intent_feed_provider import ExternalIntentFeedProvider, ExternalIntentResult
from services.quota_service import QuotaService

logger = logging.getLogger(__name__)

_PROVIDER_CONFIG = (
    ("job_postings", "JOB_INTENT_HTTP", "JOB_INTENT_URL", "JOB_INTENT_TOKEN"),
    ("company_news", "NEWS_INTENT_HTTP", "NEWS_INTENT_URL", "NEWS_INTENT_TOKEN"),
    ("social", "SOCIAL_INTENT_HTTP", "SOCIAL_INTENT_URL", "SOCIAL_INTENT_TOKEN"),
)
_PROVIDER_CONCURRENCY = 3


def _evidence_key(item: dict[str, Any]) -> tuple[str, str]:
    source = str(item.get("source") or "unknown").casefold()
    identity = item.get("external_id") or item.get("url") or item.get("title") or item.get("description") or ""
    return source, str(identity).strip().casefold()[:1000]


def _quota_enabled(quotas: Any, key: str) -> bool:
    values = quotas if isinstance(quotas, dict) else {}
    try:
        return int(values.get(key) or 0) > 0
    except (TypeError, ValueError):
        return False


def _lead_snapshot(lead: Lead, person: Person | None) -> dict[str, Any]:
    person_snapshot = None
    if person:
        person_snapshot = {
            "id": person.id,
            "name": person.name,
            "role_label": person.role_label,
            "linkedin_url": person.linkedin_url,
            "email": person.email,
            "source": person.source,
            "raw_data": deepcopy(person.raw_data) if isinstance(person.raw_data, dict) else {},
            "email_verified": bool(person.email_verified),
            "verification_status": person.verification_status,
            "email_verified_at": person.email_verified_at,
            "last_verified_at": person.last_verified_at,
        }
    return {
        "lead_id": lead.id,
        "person_id": lead.primary_person_id,
        "payload": {
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
        },
        "person": person_snapshot,
    }


def _merge_email_history(current_raw: Any, observed_raw: Any) -> dict[str, Any]:
    current = deepcopy(current_raw) if isinstance(current_raw, dict) else {}
    observed = observed_raw if isinstance(observed_raw, dict) else {}
    history = observed.get("email_verification_history")
    if isinstance(history, list):
        current["email_verification_history"] = deepcopy(history[-30:])
    return current


class ContinuousIntelligenceService:
    """Executa ciclos com I/O externo fora de transações abertas no banco."""

    def __init__(self, db: Session):
        self.db = db
        self.metrics = ProviderExecutionMetricService()

    @staticmethod
    def _quota_enabled(org: Organization, key: str) -> bool:
        return _quota_enabled(getattr(org, "api_quota", None), key)

    def _is_due(self, organization_id: Any, *, force: bool) -> bool:
        if force:
            return True
        cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.CONTINUOUS_INTELLIGENCE_MIN_INTERVAL_HOURS)
        latest = (
            self.db.query(ProviderExecutionMetric.recorded_at)
            .filter(
                ProviderExecutionMetric.organization_id == organization_id,
                ProviderExecutionMetric.provider == "continuous_intelligence",
            )
            .order_by(ProviderExecutionMetric.recorded_at.desc())
            .first()
        )
        return not latest or not latest[0] or latest[0] < cutoff

    def _record_metric(
        self,
        organization_id: Any,
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
            organization_id,
            provider,
            status,
            result_count=result_count,
            duration_ms=duration_ms,
            budget_used=1 if status not in {"disabled", "quota_exceeded"} else 0,
            error_code=error_code,
            retryable=retryable,
        )

    async def _run_provider(
        self,
        provider: ExternalIntentFeedProvider,
        payload: dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> tuple[ExternalIntentResult, int]:
        started = time.perf_counter()
        async with semaphore:
            result = await provider.collect(payload)
        return result, int((time.perf_counter() - started) * 1000)

    async def _collect_enabled_providers(
        self,
        organization_id: Any,
        quotas: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, list[dict[str, Any]]]:
        runnable: list[tuple[str, str, ExternalIntentFeedProvider]] = []
        for provider_name, quota_key, url_setting, token_setting in _PROVIDER_CONFIG:
            endpoint = str(getattr(settings, url_setting, "") or "")
            if not endpoint or not _quota_enabled(quotas, quota_key):
                continue
            if not QuotaService.can_consume(self.db, str(organization_id), quota_key):
                self._record_metric(organization_id, provider_name, "quota_exceeded", error_code="daily_quota")
                continue
            runnable.append((
                provider_name,
                quota_key,
                ExternalIntentFeedProvider(
                    name=provider_name,
                    endpoint=endpoint,
                    token=str(getattr(settings, token_setting, "") or ""),
                    max_retries=settings.INTENT_PROVIDER_MAX_RETRIES,
                ),
            ))

        self.db.commit()
        if not runnable:
            return {}

        semaphore = asyncio.Semaphore(_PROVIDER_CONCURRENCY)
        results = await asyncio.gather(*[
            self._run_provider(provider, payload, semaphore)
            for _, _, provider in runnable
        ])

        collected: dict[str, list[dict[str, Any]]] = {}
        for (provider_name, quota_key, _provider), (result, duration_ms) in zip(runnable, results):
            QuotaService.consume(self.db, str(organization_id), quota_key)
            self._record_metric(
                organization_id,
                provider_name,
                result.status,
                result_count=len(result.evidence),
                duration_ms=duration_ms,
                error_code=result.error_code,
                retryable=result.retryable,
            )
            collected[provider_name] = list(result.evidence)
        self.db.commit()
        return collected

    async def _verify_email_if_enabled(
        self,
        organization_id: Any,
        quotas: dict[str, Any],
        person_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not person_snapshot or not person_snapshot.get("email"):
            return None
        quota_key = "EMAIL_CATCHALL_PROBE"
        if not settings.EMAIL_CATCHALL_PROBE_ENABLED or not _quota_enabled(quotas, quota_key):
            return None
        if not QuotaService.can_consume(self.db, str(organization_id), quota_key):
            self._record_metric(organization_id, "email_catchall", "quota_exceeded", error_code="daily_quota")
            self.db.commit()
            return None

        target = SimpleNamespace(**deepcopy(person_snapshot))
        self.db.commit()
        started = time.perf_counter()
        verifier = ContactVerifier(EmailVerificationService(), enable_catchall_probe=True)
        result = await verifier.verify_email(target)
        QuotaService.consume(self.db, str(organization_id), quota_key)
        status = str(result.get("verification_status") or "unknown")
        self._record_metric(
            organization_id,
            "email_catchall",
            "success" if status in {"non_catch_all", "catch_all", "domain_validated"} else "empty",
            result_count=1,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        self.db.commit()
        return {"result": result, "raw_data": deepcopy(getattr(target, "raw_data", {}) or {})}

    def _persist_observations(
        self,
        organization_id: Any,
        snapshot: dict[str, Any],
        provider_results: dict[str, list[dict[str, Any]]],
        email_observation: dict[str, Any] | None,
    ) -> bool:
        lead = self.db.query(Lead).filter(
            Lead.id == snapshot["lead_id"],
            Lead.organization_id == organization_id,
        ).first()
        if lead is None or lead.opt_out:
            return False

        person = None
        if snapshot.get("person_id"):
            person = self.db.query(Person).filter(
                Person.id == snapshot["person_id"],
                Person.organization_id == organization_id,
            ).first()

        existing = [item for item in (lead.evidence or []) if isinstance(item, dict)] if isinstance(lead.evidence, list) else []
        known = {_evidence_key(item) for item in existing}
        new_evidence: list[dict[str, Any]] = []

        for provider_name, values in provider_results.items():
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

        if person and email_observation:
            result = email_observation["result"]
            previously_verified = ContactVerifier.has_authoritative_verification(person)
            previous_status = person.verification_status
            previous_verified_at = person.email_verified_at
            person.raw_data = _merge_email_history(person.raw_data, email_observation.get("raw_data"))
            if previously_verified and result.get("passive_observation"):
                person.email_verified = True
                person.verification_status = previous_status
                person.email_verified_at = previous_verified_at
            else:
                person.email_verified = bool(result.get("email_verified"))
                person.verification_status = str(result.get("verification_status") or "unknown")
                if person.email_verified:
                    person.email_verified_at = datetime.now(timezone.utc)
            self.db.add(person)

        if not new_evidence:
            self.db.commit()
            return False

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
        DataIntelligenceService(self.db, organization_id).analyze_lead(lead, persist=True)
        return True

    async def run_once_for_org(self, org: Organization, *, force: bool = False) -> dict[str, Any]:
        organization_id = org.id
        quotas = deepcopy(org.api_quota) if isinstance(org.api_quota, dict) else {}
        if not _quota_enabled(quotas, "CONTINUOUS_INTELLIGENCE"):
            return {"organization_id": str(organization_id), "status": "disabled", "processed": 0, "changed": 0}
        if not self._is_due(organization_id, force=force):
            return {"organization_id": str(organization_id), "status": "not_due", "processed": 0, "changed": 0}
        if not QuotaService.can_consume(self.db, str(organization_id), "CONTINUOUS_INTELLIGENCE"):
            return {"organization_id": str(organization_id), "status": "quota_exceeded", "processed": 0, "changed": 0}

        leads = (
            self.db.query(Lead)
            .filter(Lead.organization_id == organization_id, Lead.opt_out.is_(False))
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
                .filter(Person.organization_id == organization_id, Person.id.in_(person_ids))
                .all()
            }
        snapshots = [_lead_snapshot(lead, people.get(lead.primary_person_id)) for lead in leads]
        self.db.commit()

        processed = 0
        changed = 0
        for snapshot in snapshots:
            provider_results = await self._collect_enabled_providers(
                organization_id,
                quotas,
                snapshot["payload"],
            )
            email_observation = await self._verify_email_if_enabled(
                organization_id,
                quotas,
                snapshot.get("person"),
            )
            if self._persist_observations(organization_id, snapshot, provider_results, email_observation):
                changed += 1
            processed += 1

        QuotaService.consume(self.db, str(organization_id), "CONTINUOUS_INTELLIGENCE")
        self._record_metric(organization_id, "continuous_intelligence", "success", result_count=changed)
        self.db.commit()
        return {
            "organization_id": str(organization_id),
            "status": "success",
            "processed": processed,
            "changed": changed,
        }

    async def run_due_organizations(self) -> list[dict[str, Any]]:
        rows = self.db.query(Organization.id, Organization.api_quota).order_by(Organization.created_at.asc()).all()
        org_snapshots = [SimpleNamespace(id=row[0], api_quota=deepcopy(row[1]) if isinstance(row[1], dict) else {}) for row in rows]
        self.db.commit()

        results: list[dict[str, Any]] = []
        for org in org_snapshots:
            if not self._quota_enabled(org, "CONTINUOUS_INTELLIGENCE"):
                continue
            try:
                results.append(await self.run_once_for_org(org))
            except Exception as exc:  # noqa: BLE001
                self.db.rollback()
                logger.error("Inteligência contínua falhou na org %s: %s", org.id, exc)
                results.append({"organization_id": str(org.id), "status": "failed", "error": type(exc).__name__})
        return results
