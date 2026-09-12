"""Sincronização CRM tenant-aware, idempotente e conservadora.

A saída usa entidades canônicas e links persistentes. A entrada só altera
campos explicitamente seguros em entidades já vinculadas; objetos remotos sem
vínculo ou campos ambíguos viram conflitos auditáveis em vez de sobrescrever
dados locais por heurística.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from database.crm_models import CRMConnection, CRMExternalLink, CRMSyncRun
from services.crm_adapters import CRMEntitySnapshot, build_crm_adapter
from services.secret_service import SecretService
from src.db.models import Company, Lead, LeadOpportunityRow, Person


SECRET_BY_PROVIDER = {
    "pipedrive": "PIPEDRIVE_API_TOKEN",
    "hubspot": "HUBSPOT_ACCESS_TOKEN",
    "salesforce": "SALESFORCE_ACCESS_TOKEN",
}
SYNC_MODES = {"manual", "realtime", "scheduled"}


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class CRMSyncService:
    def __init__(self, db: Session, organization_id: Any):
        self.db = db
        self.organization_id = organization_id

    async def configure(
        self,
        *,
        provider: str,
        sync_mode: str,
        token: str | None = None,
        base_url: str | None = None,
        enabled: bool = False,
    ) -> CRMConnection:
        normalized = provider.strip().lower()
        if normalized not in SECRET_BY_PROVIDER:
            raise ValueError("Sistema comercial não suportado")
        if sync_mode not in SYNC_MODES:
            raise ValueError("Modo de sincronização inválido")
        if base_url and not base_url.lower().startswith("https://"):
            raise ValueError("A URL da integração deve usar HTTPS")
        key_name = SECRET_BY_PROVIDER[normalized]
        if token is not None:
            if len(token.strip()) < 8:
                raise ValueError("Credencial inválida")
            await SecretService.set_org_secret(self.db, str(self.organization_id), key_name, token.strip())

        row = self.db.query(CRMConnection).filter(
            CRMConnection.organization_id == self.organization_id,
            CRMConnection.provider == normalized,
        ).first()
        if not row:
            row = CRMConnection(
                organization_id=self.organization_id,
                provider=normalized,
                secret_key_name=key_name,
            )
            self.db.add(row)
        row.sync_mode = sync_mode
        row.base_url = base_url.strip() if base_url else None
        row.enabled = bool(enabled)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_connections(self) -> list[CRMConnection]:
        return self.db.query(CRMConnection).filter(
            CRMConnection.organization_id == self.organization_id,
        ).order_by(CRMConnection.provider.asc()).all()

    async def healthcheck(self, connection_id: Any) -> dict[str, Any]:
        connection, adapter = await self._adapter(connection_id)
        try:
            result = await adapter.healthcheck()
            connection.last_health_status = str(result.get("status") or "unknown")[:32]
        except Exception as exc:
            connection.last_health_status = "failed"
            connection.last_health_at = datetime.now(timezone.utc)
            self.db.commit()
            return {"provider": connection.provider, "status": "failed", "detail": str(exc)[:300]}
        connection.last_health_at = datetime.now(timezone.utc)
        self.db.commit()
        return {"provider": connection.provider, "status": connection.last_health_status}

    async def push_lead(self, connection_id: Any, lead_id: Any, *, idempotency_key: str) -> dict[str, Any]:
        connection, adapter = await self._adapter(connection_id)
        lead = self.db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.organization_id == self.organization_id,
        ).first()
        if not lead:
            raise LookupError("Oportunidade não encontrada")
        snapshots = self._snapshots_for_lead(lead, connection.provider)
        run = self._start_run(connection, "outbound", idempotency_key)
        if run.status != "RUNNING":
            return run.result or {"status": run.status.lower()}

        results: list[dict[str, Any]] = []
        try:
            for snapshot in snapshots:
                run.processed += 1
                link = self._link(connection.provider, snapshot.entity_type, snapshot.entity_id)
                fields = dict(snapshot.fields)
                if link:
                    fields["_remote_id"] = link.remote_entity_id
                    snapshot = CRMEntitySnapshot(
                        snapshot.entity_type,
                        snapshot.entity_id,
                        snapshot.organization_id,
                        fields=fields,
                        updated_at=snapshot.updated_at,
                    )
                result = await adapter.upsert(snapshot, idempotency_key=f"{idempotency_key}:{snapshot.entity_type}:{snapshot.entity_id}")
                results.append({
                    "entity_type": snapshot.entity_type,
                    "local_id": snapshot.entity_id,
                    "remote_id": result.remote_entity_id,
                    "status": result.status,
                })
                if result.status == "success" and result.remote_entity_id:
                    run.succeeded += 1
                    self._upsert_link(connection.provider, snapshot, result.remote_entity_id, result.remote_version)
                elif result.status == "unsupported":
                    run.conflicts += 1
                else:
                    run.failed += 1
            run.status = "COMPLETED" if run.failed == 0 else "PARTIAL"
            run.result = {"items": results}
            run.completed_at = datetime.now(timezone.utc)
            connection.last_sync_at = run.completed_at
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            run = self.db.query(CRMSyncRun).filter(CRMSyncRun.id == run.id).first()
            if run:
                run.status = "FAILED"
                run.error_message = str(exc)[:2000]
                run.completed_at = datetime.now(timezone.utc)
                self.db.commit()
            raise
        return {"status": run.status.lower(), "items": results, "processed": run.processed, "succeeded": run.succeeded, "failed": run.failed, "conflicts": run.conflicts}

    async def pull_changes(self, connection_id: Any, *, idempotency_key: str) -> dict[str, Any]:
        connection, adapter = await self._adapter(connection_id)
        run = self._start_run(connection, "inbound", idempotency_key)
        if run.status != "RUNNING":
            return run.result or {"status": run.status.lower()}
        changes, next_cursor = await adapter.fetch_changes(organization_id=str(self.organization_id), cursor=connection.cursor)
        details: list[dict[str, Any]] = []
        for snapshot in changes:
            run.processed += 1
            remote_id = str(snapshot.fields.get("_remote_id") or "")
            link = self.db.query(CRMExternalLink).filter(
                CRMExternalLink.organization_id == self.organization_id,
                CRMExternalLink.provider == connection.provider,
                CRMExternalLink.entity_type == snapshot.entity_type,
                CRMExternalLink.remote_entity_id == remote_id,
            ).first() if remote_id else None
            if not link:
                run.conflicts += 1
                details.append({"entity_type": snapshot.entity_type, "remote_id": remote_id or None, "status": "review_required", "reason": "sem vínculo local confiável"})
                continue
            changed = self._apply_safe_remote_fields(snapshot.entity_type, link.local_entity_id, dict(snapshot.fields), connection.provider)
            if changed:
                run.succeeded += 1
                link.last_remote_hash = _fingerprint(dict(snapshot.fields))
                link.last_synced_at = datetime.now(timezone.utc)
                details.append({"entity_type": snapshot.entity_type, "remote_id": remote_id, "status": "updated"})
            else:
                details.append({"entity_type": snapshot.entity_type, "remote_id": remote_id, "status": "no_safe_changes"})
        connection.cursor = next_cursor
        run.status = "COMPLETED"
        run.result = {"items": details, "next_cursor": next_cursor}
        run.completed_at = datetime.now(timezone.utc)
        connection.last_sync_at = run.completed_at
        self.db.commit()
        return {"status": "completed", "items": details, "processed": run.processed, "succeeded": run.succeeded, "conflicts": run.conflicts}

    async def _adapter(self, connection_id: Any):
        connection = self.db.query(CRMConnection).filter(
            CRMConnection.id == connection_id,
            CRMConnection.organization_id == self.organization_id,
        ).first()
        if not connection:
            raise LookupError("Integração não encontrada")
        if not connection.enabled:
            raise ValueError("Integração está desativada")
        token = await SecretService.resolve_key(self.db, str(self.organization_id), connection.secret_key_name)
        if not token:
            raise ValueError("Credencial da integração não configurada")
        adapter = build_crm_adapter(connection.provider, token, base_url=connection.base_url)
        return connection, adapter

    def _start_run(self, connection: CRMConnection, direction: str, idempotency_key: str) -> CRMSyncRun:
        if not idempotency_key or len(idempotency_key) > 180:
            raise ValueError("Chave de idempotência inválida")
        existing = self.db.query(CRMSyncRun).filter(
            CRMSyncRun.organization_id == self.organization_id,
            CRMSyncRun.idempotency_key == idempotency_key,
        ).first()
        if existing:
            return existing
        run = CRMSyncRun(
            organization_id=self.organization_id,
            connection_id=connection.id,
            direction=direction,
            idempotency_key=idempotency_key,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def _snapshots_for_lead(self, lead: Lead, provider: str) -> list[CRMEntitySnapshot]:
        snapshots: list[CRMEntitySnapshot] = []
        company = None
        if lead.company_id:
            company = self.db.query(Company).filter(
                Company.id == lead.company_id,
                Company.organization_id == self.organization_id,
            ).first()
        if company:
            fields = self._company_fields(company, provider)
            snapshots.append(CRMEntitySnapshot("company", str(company.id), str(self.organization_id), fields=fields, updated_at=company.updated_at.isoformat() if company.updated_at else None))
        if lead.primary_person_id:
            person = self.db.query(Person).filter(
                Person.id == lead.primary_person_id,
                Person.organization_id == self.organization_id,
            ).first()
            if person:
                snapshots.append(CRMEntitySnapshot("person", str(person.id), str(self.organization_id), fields=self._person_fields(person, provider), updated_at=person.updated_at.isoformat() if person.updated_at else None))
        opportunities = self.db.query(LeadOpportunityRow).filter(
            LeadOpportunityRow.lead_id == lead.id,
            LeadOpportunityRow.organization_id == self.organization_id,
        ).all()
        for opportunity in opportunities:
            snapshots.append(CRMEntitySnapshot("opportunity", str(opportunity.id), str(self.organization_id), fields=self._opportunity_fields(lead, opportunity, provider), updated_at=opportunity.updated_at.isoformat() if opportunity.updated_at else None))
        return snapshots

    @staticmethod
    def _company_fields(company: Company, provider: str) -> dict[str, Any]:
        if provider == "hubspot":
            return {"name": company.company_name, "website": company.website, "phone": company.phone, "city": company.city, "state": company.state}
        if provider == "salesforce":
            return {"Name": company.company_name, "Website": company.website, "Phone": company.phone, "BillingCity": company.city, "BillingState": company.state}
        return {"name": company.company_name, "address": company.address}

    @staticmethod
    def _person_fields(person: Person, provider: str) -> dict[str, Any]:
        if provider == "hubspot":
            parts = person.name.strip().split(maxsplit=1)
            return {"firstname": parts[0] if parts else person.name, "lastname": parts[1] if len(parts) > 1 else "", "email": person.email, "phone": person.phone}
        if provider == "salesforce":
            parts = person.name.strip().split(maxsplit=1)
            return {"FirstName": parts[0] if len(parts) > 1 else None, "LastName": parts[-1] if parts else person.name, "Email": person.email, "Phone": person.phone}
        return {"name": person.name, "email": [{"value": person.email, "primary": True}] if person.email else [], "phone": [{"value": person.phone, "primary": True}] if person.phone else []}

    @staticmethod
    def _opportunity_fields(lead: Lead, opportunity: LeadOpportunityRow, provider: str) -> dict[str, Any]:
        title = f"{lead.company_name or 'Oportunidade'} — {opportunity.offer_key}"
        if provider == "hubspot":
            return {"dealname": title, "prospect_ai_score": opportunity.score, "prospect_ai_offer": opportunity.offer_key}
        if provider == "salesforce":
            # Salesforce exige StageName/CloseDate para criação de Opportunity;
            # sem mapeamento explícito do workspace não inventamos esses valores.
            return {"Name": title, "Prospect_AI_Score__c": opportunity.score, "Prospect_AI_Offer__c": opportunity.offer_key}
        return {"title": title, "probability": min(100, max(0, int(opportunity.score or 0)))}

    def _link(self, provider: str, entity_type: str, local_id: str) -> CRMExternalLink | None:
        return self.db.query(CRMExternalLink).filter(
            CRMExternalLink.organization_id == self.organization_id,
            CRMExternalLink.provider == provider,
            CRMExternalLink.entity_type == entity_type,
            CRMExternalLink.local_entity_id == local_id,
        ).first()

    def _upsert_link(self, provider: str, snapshot: CRMEntitySnapshot, remote_id: str, remote_version: str | None) -> None:
        link = self._link(provider, snapshot.entity_type, snapshot.entity_id)
        if not link:
            link = CRMExternalLink(
                organization_id=self.organization_id,
                provider=provider,
                entity_type=snapshot.entity_type,
                local_entity_id=snapshot.entity_id,
                remote_entity_id=remote_id,
            )
            self.db.add(link)
        link.remote_entity_id = remote_id
        link.remote_version = remote_version
        link.last_local_hash = _fingerprint(dict(snapshot.fields))
        link.last_synced_at = datetime.now(timezone.utc)
        self.db.flush()

    def _apply_safe_remote_fields(self, entity_type: str, local_id: str, fields: dict[str, Any], provider: str) -> bool:
        if entity_type == "company":
            row = self.db.query(Company).filter(Company.id == local_id, Company.organization_id == self.organization_id).first()
            if not row:
                return False
            mapping = {"hubspot": {"name": "company_name", "website": "website", "phone": "phone", "city": "city", "state": "state"}, "pipedrive": {"name": "company_name", "address": "address"}, "salesforce": {"Name": "company_name", "Website": "website", "Phone": "phone", "BillingCity": "city", "BillingState": "state"}}.get(provider, {})
        elif entity_type == "person":
            row = self.db.query(Person).filter(Person.id == local_id, Person.organization_id == self.organization_id).first()
            if not row:
                return False
            mapping = {"hubspot": {"email": "email", "phone": "phone"}, "salesforce": {"Email": "email", "Phone": "phone"}}.get(provider, {})
        else:
            return False
        changed = False
        for remote_field, local_field in mapping.items():
            value = fields.get(remote_field)
            if value in (None, ""):
                continue
            current = getattr(row, local_field, None)
            # Remote sync can fill missing canonical data, but never silently
            # replace an existing local value. Divergence is a review concern.
            if current in (None, ""):
                setattr(row, local_field, value)
                changed = True
        if changed:
            self.db.add(row)
        return changed
