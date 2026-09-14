"""Ações globais em massa do CRM que não pertencem ao comando de status/owner.

Mantém `Lead`, `CommercialTask`, `SequenceEnrollment` e `Campaign` como fontes
canônicas. `CommercialBulkOperation` é somente ledger de idempotência; tags e
arquivamento ficam na extensão 1:1 `LeadCrmMetadata`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any
import uuid

from sqlalchemy.exc import IntegrityError

from database.crm_models import CrmEntityAudit, LeadCrmMetadata
from database.engagement_models import SequenceEnrollment, SequenceExecution, SequenceTemplate
from src.db.models import Campaign, CommercialBulkOperation, Lead, NegotiationStage, OrganizationMember, SalesRole, User
from src.services.org_service import consultant_lead_scope

MAX_ITEMS = 100
OPERATIONS = {"negotiation_stage", "campaign", "add_tag", "remove_tag", "archive", "unarchive", "start_sequence"}


class OperatingBulkValidation(ValueError): pass
class OperatingBulkForbidden(PermissionError): pass
class OperatingBulkConflict(RuntimeError): pass


def _as_uuid(value: Any, field: str) -> uuid.UUID:
    try: return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc: raise OperatingBulkValidation(f"{field} inválido") from exc


def _parse_dt(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip(): raise OperatingBulkValidation("expected_updated_at inválido")
    try: parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc: raise OperatingBulkValidation("expected_updated_at inválido") from exc
    if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_tag(value: Any) -> str:
    tag = " ".join(str(value or "").strip().split())
    if not 1 <= len(tag) <= 40: raise OperatingBulkValidation("tag deve ter entre 1 e 40 caracteres")
    return tag


def normalize_operating_bulk_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"operation", "lead_ids", "expected_updated_at", "negotiation_stage", "campaign_id", "tag", "sequence_id"}
    unknown = sorted(set(payload) - allowed)
    if unknown: raise OperatingBulkValidation("Campo(s) não permitido(s): " + ", ".join(unknown))
    operation = str(payload.get("operation") or "").strip().lower()
    if operation not in OPERATIONS: raise OperatingBulkValidation("operation inválida")
    raw_ids = payload.get("lead_ids")
    if not isinstance(raw_ids, list) or not 1 <= len(raw_ids) <= MAX_ITEMS: raise OperatingBulkValidation(f"lead_ids deve conter entre 1 e {MAX_ITEMS} itens")
    ids = [str(_as_uuid(item, "lead_id")) for item in raw_ids]
    if len(ids) != len(set(ids)): raise OperatingBulkValidation("lead_ids não pode conter duplicatas")
    raw_expected = payload.get("expected_updated_at")
    if not isinstance(raw_expected, dict): raise OperatingBulkValidation("expected_updated_at deve ser um mapa")
    expected: dict[str, str] = {}
    for lead_id in ids:
        if lead_id not in raw_expected: raise OperatingBulkValidation("expected_updated_at deve conter todos os leads")
        expected[lead_id] = _parse_dt(raw_expected[lead_id]).isoformat()
    result: dict[str, Any] = {"operation": operation, "lead_ids": ids, "expected_updated_at": dict(sorted(expected.items())), "negotiation_stage": None, "campaign_id": None, "tag": None, "sequence_id": None}
    if operation == "negotiation_stage":
        raw = payload.get("negotiation_stage")
        if raw not in (None, ""):
            try: result["negotiation_stage"] = NegotiationStage(str(raw)).value
            except ValueError as exc: raise OperatingBulkValidation("negotiation_stage inválido") from exc
    elif operation == "campaign": result["campaign_id"] = str(_as_uuid(payload.get("campaign_id"), "campaign_id"))
    elif operation in {"add_tag", "remove_tag"}: result["tag"] = _normalize_tag(payload.get("tag"))
    elif operation == "start_sequence": result["sequence_id"] = str(_as_uuid(payload.get("sequence_id"), "sequence_id"))
    return result


def _fingerprint(payload: dict[str, Any]) -> str:
    normalized = normalize_operating_bulk_payload(payload)
    return hashlib.sha256(json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _replay(row: CommercialBulkOperation, fingerprint: str) -> dict[str, Any]:
    if row.payload_hash != fingerprint: raise OperatingBulkConflict("idempotency_key já usada com outro payload")
    if row.status != "COMPLETED" or not row.result: raise OperatingBulkConflict("operação idempotente ainda está em andamento")
    value = dict(row.result); value["replayed"] = True; return value


class SalesOperatingBulkService:
    def __init__(self, db, organization_id: Any, member: OrganizationMember, user: User):
        self.db, self.organization_id, self.member, self.user = db, organization_id, member, user

    def _assert_write(self) -> None:
        if self.member.sales_role == SalesRole.ANALYST: raise OperatingBulkForbidden("ANALYST possui acesso somente de leitura")

    def _plan(self, normalized: dict[str, Any], lock: bool = False) -> dict[str, Any]:
        query = self.db.query(Lead).filter(Lead.organization_id == self.organization_id, Lead.id.in_([uuid.UUID(item) for item in normalized["lead_ids"]]))
        query = consultant_lead_scope(self.member, query)
        if lock: query = query.with_for_update()
        rows = query.all(); by_id = {str(row.id): row for row in rows}; accepted = []; rejected = []
        for lead_id in normalized["lead_ids"]:
            row = by_id.get(lead_id)
            if row is None: rejected.append({"id": lead_id, "reason": "NOT_FOUND_OR_UNAUTHORIZED"}); continue
            current = row.updated_at
            if current is None: rejected.append({"id": lead_id, "reason": "VERSION_CONFLICT"}); continue
            if current.tzinfo is None: current = current.replace(tzinfo=timezone.utc)
            if current != _parse_dt(normalized["expected_updated_at"][lead_id]): rejected.append({"id": lead_id, "reason": "VERSION_CONFLICT"}); continue
            accepted.append(lead_id)
        return {"accepted_ids": accepted, "rejected": rejected, "_rows": by_id}

    def preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._assert_write(); normalized = normalize_operating_bulk_payload(payload); self._validate_reference(normalized); plan = self._plan(normalized)
        return {"operation": normalized["operation"], "total_selected": len(normalized["lead_ids"]), "accepted_ids": plan["accepted_ids"], "rejected": plan["rejected"], "max_items": MAX_ITEMS}

    def _validate_reference(self, normalized: dict[str, Any]) -> None:
        if normalized["operation"] == "campaign":
            exists = self.db.query(Campaign.id).filter(Campaign.id == uuid.UUID(normalized["campaign_id"]), Campaign.organization_id == self.organization_id).first()
            if not exists: raise OperatingBulkValidation("Campanha não pertence ao workspace")
        elif normalized["operation"] == "start_sequence":
            exists = self.db.query(SequenceTemplate.id).filter(SequenceTemplate.id == uuid.UUID(normalized["sequence_id"]), SequenceTemplate.organization_id == self.organization_id, SequenceTemplate.enabled.is_(True)).first()
            if not exists: raise OperatingBulkValidation("Sequência não pertence ao workspace ou está desativada")

    def _metadata(self, lead: Lead) -> LeadCrmMetadata:
        row = self.db.query(LeadCrmMetadata).filter(LeadCrmMetadata.organization_id == self.organization_id, LeadCrmMetadata.lead_id == lead.id).first()
        if row is None:
            row = LeadCrmMetadata(organization_id=self.organization_id, lead_id=lead.id, tags=[]); self.db.add(row); self.db.flush()
        return row

    def _audit(self, lead: Lead, action: str, changes: dict[str, Any]) -> None:
        self.db.add(CrmEntityAudit(organization_id=self.organization_id, actor_id=self.user.id, entity_type="lead", entity_id=str(lead.id), action=action, changes=changes))

    def _start_sequence(self, lead: Lead, sequence_id: str, now: datetime) -> tuple[str, str | None]:
        template = self.db.query(SequenceTemplate).filter(SequenceTemplate.id == uuid.UUID(sequence_id), SequenceTemplate.organization_id == self.organization_id, SequenceTemplate.enabled.is_(True)).first()
        if template is None: return "failed", "SEQUENCE_NOT_FOUND"
        if lead.opt_out: return "rejected", "LEAD_OPT_OUT"
        existing = self.db.query(SequenceEnrollment).filter(SequenceEnrollment.organization_id == self.organization_id, SequenceEnrollment.sequence_id == template.id, SequenceEnrollment.lead_id == lead.id).first()
        if existing is not None: return "duplicate", "ALREADY_ENROLLED"
        enrollment = SequenceEnrollment(organization_id=self.organization_id, sequence_id=template.id, lead_id=lead.id, person_id=lead.primary_person_id, enrolled_by_id=self.user.id, status="ACTIVE", current_step_index=0)
        self.db.add(enrollment); self.db.flush()
        scheduled = now
        for index, step in enumerate(template.steps or []):
            scheduled += timedelta(minutes=int(step.get("delay_minutes") or 0))
            self.db.add(SequenceExecution(organization_id=self.organization_id, enrollment_id=enrollment.id, lead_id=lead.id, step_index=index, step_type=step["type"], scheduled_at=scheduled, payload=step, idempotency_key=f"sequence:{enrollment.id}:{index}"))
        if template.steps:
            enrollment.next_action_at = now + timedelta(minutes=int(template.steps[0].get("delay_minutes") or 0))
        self._audit(lead, "START_SEQUENCE", {"sequence_id": sequence_id, "enrollment_id": str(enrollment.id)})
        return "accepted", None

    def _apply(self, lead: Lead, normalized: dict[str, Any]) -> tuple[str, str | None]:
        operation = normalized["operation"]; now = datetime.now(timezone.utc)
        if operation == "negotiation_stage":
            new_value = NegotiationStage(normalized["negotiation_stage"]) if normalized["negotiation_stage"] else None; old = getattr(lead.negotiation_stage, "value", lead.negotiation_stage)
            if old == normalized["negotiation_stage"]: return "duplicate", "ALREADY_IN_DESIRED_STATE"
            lead.negotiation_stage = new_value; self._audit(lead, "NEGOTIATION_STAGE", {"from": old, "to": normalized["negotiation_stage"]})
        elif operation == "campaign":
            new_id = uuid.UUID(normalized["campaign_id"])
            if lead.campaign_id == new_id: return "duplicate", "ALREADY_IN_DESIRED_STATE"
            old = str(lead.campaign_id) if lead.campaign_id else None; lead.campaign_id = new_id; self._audit(lead, "CAMPAIGN", {"from": old, "to": str(new_id)})
        elif operation in {"add_tag", "remove_tag"}:
            metadata = self._metadata(lead); tags = list(metadata.tags or []); target = normalized["tag"]; indexes = {str(value).casefold(): index for index, value in enumerate(tags)}; folded = target.casefold()
            if operation == "add_tag":
                if folded in indexes: return "duplicate", "ALREADY_IN_DESIRED_STATE"
                if len(tags) >= 30: return "rejected", "TAG_LIMIT_REACHED"
                tags.append(target)
            else:
                if folded not in indexes: return "duplicate", "ALREADY_IN_DESIRED_STATE"
                tags.pop(indexes[folded])
            metadata.tags = tags; self._audit(lead, operation.upper(), {"tag": target})
        elif operation in {"archive", "unarchive"}:
            metadata = self._metadata(lead)
            if operation == "archive":
                if metadata.archived_at is not None: return "duplicate", "ALREADY_IN_DESIRED_STATE"
                metadata.archived_at = now; metadata.archived_by_id = self.user.id
            else:
                if metadata.archived_at is None: return "duplicate", "ALREADY_IN_DESIRED_STATE"
                metadata.archived_at = None; metadata.archived_by_id = None
            self._audit(lead, operation.upper(), {})
        elif operation == "start_sequence":
            status, reason = self._start_sequence(lead, normalized["sequence_id"], now)
            if status != "accepted": return status, reason
        lead.updated_at = now
        return "accepted", None

    def execute(self, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        self._assert_write()
        if not isinstance(idempotency_key, str) or not 8 <= len(idempotency_key) <= 160: raise OperatingBulkValidation("idempotency_key deve ter entre 8 e 160 caracteres")
        normalized = normalize_operating_bulk_payload(payload); self._validate_reference(normalized); fingerprint = _fingerprint(normalized)
        existing = self.db.query(CommercialBulkOperation).filter(CommercialBulkOperation.organization_id == self.organization_id, CommercialBulkOperation.idempotency_key == idempotency_key).first()
        if existing is not None: return _replay(existing, fingerprint)
        ledger = CommercialBulkOperation(organization_id=self.organization_id, actor_id=self.user.id, idempotency_key=idempotency_key, operation=f"crm:{normalized['operation']}", payload_hash=fingerprint, status="RUNNING", created_at=datetime.now(timezone.utc)); self.db.add(ledger)
        try: self.db.flush()
        except IntegrityError:
            self.db.rollback(); winner = self.db.query(CommercialBulkOperation).filter(CommercialBulkOperation.organization_id == self.organization_id, CommercialBulkOperation.idempotency_key == idempotency_key).first()
            if winner is None: raise OperatingBulkConflict("conflito idempotente sem operação vencedora")
            return _replay(winner, fingerprint)
        plan = self._plan(normalized, lock=True); results = [{"id": item["id"], "status": "rejected", "reason": item["reason"]} for item in plan["rejected"]]
        for lead_id in plan["accepted_ids"]:
            lead = plan["_rows"][lead_id]
            try:
                status, reason = self._apply(lead, normalized); results.append({"id": lead_id, "status": status, "reason": reason})
            except (ValueError, LookupError, IntegrityError) as exc:
                self.db.rollback()
                raise OperatingBulkConflict("Falha transacional ao aplicar operação em massa") from exc
        summary = {"accepted": sum(item["status"] == "accepted" for item in results), "duplicate": sum(item["status"] == "duplicate" for item in results), "rejected": sum(item["status"] == "rejected" for item in results), "failed": sum(item["status"] == "failed" for item in results)}
        result = {"operation": normalized["operation"], "items": results, "summary": summary, "replayed": False}; ledger.status = "COMPLETED"; ledger.result = result; ledger.completed_at = datetime.now(timezone.utc); self.db.commit(); return result
