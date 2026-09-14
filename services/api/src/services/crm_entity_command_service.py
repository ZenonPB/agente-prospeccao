"""Comandos tenant-safe para as entidades canônicas do CRM.

Company e Person continuam sendo as fontes de verdade. Este serviço apenas
permite edição humana controlada, com concorrência otimista e auditoria
append-only; chaves fortes de identidade (CNPJ/CPF) não são alteradas aqui.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from database.crm_models import CrmEntityAudit
from services.domain_utils import normalize_domain
from src.db.models import Company, ContactRole, Lead, Person, SalesRole
from src.services.org_service import consultant_lead_scope, is_full_access


class CrmEntityValidation(ValueError):
    pass


class CrmEntityForbidden(PermissionError):
    pass


class CrmEntityConflict(RuntimeError):
    pass


def _as_uuid(value: Any, field: str) -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise CrmEntityValidation(f"{field} inválido") from exc


def _parse_expected(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise CrmEntityValidation("expected_updated_at é obrigatório")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise CrmEntityValidation("expected_updated_at inválido") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _clean_optional(value: Any, max_length: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > max_length:
        raise CrmEntityValidation(f"valor excede {max_length} caracteres")
    return text


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return getattr(value, "value", value)


class CrmEntityCommandService:
    COMPANY_FIELDS = {
        "company_name", "name", "website", "phone", "address", "city", "state",
        "country", "category", "company_linkedin_url", "instagram_url",
    }
    PERSON_FIELDS = {
        "name", "role", "role_label", "email", "phone", "linkedin_url",
        "verification_status", "routability_type", "routable", "routability_reason",
    }

    def __init__(self, db, organization_id: Any, member: Any, user: Any):
        self.db = db
        self.organization_id = organization_id
        self.member = member
        self.user = user

    def _assert_write_role(self) -> None:
        if self.member.sales_role == SalesRole.ANALYST:
            raise CrmEntityForbidden("ANALYST possui acesso somente de leitura")

    def _company_visible(self, company_id: uuid.UUID) -> Company | None:
        company = self.db.query(Company).filter(
            Company.id == company_id,
            Company.organization_id == self.organization_id,
        ).first()
        if company is None:
            return None
        if is_full_access(self.member):
            return company
        lead = consultant_lead_scope(
            self.member,
            self.db.query(Lead).filter(
                Lead.organization_id == self.organization_id,
                Lead.company_id == company.id,
            ),
        ).first()
        return company if lead is not None else None

    def _person_visible(self, person_id: uuid.UUID) -> Person | None:
        person = self.db.query(Person).filter(
            Person.id == person_id,
            Person.organization_id == self.organization_id,
        ).first()
        if person is None:
            return None
        if is_full_access(self.member):
            return person
        visible = consultant_lead_scope(
            self.member,
            self.db.query(Lead).filter(
                Lead.organization_id == self.organization_id,
                Lead.company_id == person.company_id,
            ),
        ).first()
        return person if visible is not None else None

    @staticmethod
    def _assert_version(row: Any, expected: Any) -> None:
        parsed = _parse_expected(expected)
        # Company/Person legados nasceram antes de updated_at possuir default.
        # A criação é uma versão inicial estável; após a primeira escrita,
        # updated_at passa a ser a autoridade de concorrência otimista.
        current = row.updated_at or row.created_at
        if current is None:
            raise CrmEntityConflict("Registro sem versão de concorrência; recarregue antes de editar")
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        if current != parsed.astimezone(timezone.utc):
            raise CrmEntityConflict("Registro foi alterado por outra operação; recarregue e tente novamente")

    def _audit(self, entity_type: str, entity_id: Any, changes: dict[str, Any]) -> None:
        self.db.add(CrmEntityAudit(
            organization_id=self.organization_id,
            actor_id=self.user.id,
            entity_type=entity_type,
            entity_id=str(entity_id),
            action="UPDATE",
            changes=changes,
        ))

    def update_company(self, company_id: Any, *, expected_updated_at: Any, values: dict[str, Any]) -> Company:
        self._assert_write_role()
        unknown = sorted(set(values) - self.COMPANY_FIELDS)
        if unknown:
            raise CrmEntityValidation("Campo(s) não editável(is): " + ", ".join(unknown))
        if not values:
            raise CrmEntityValidation("Informe ao menos um campo para atualizar")
        row = self._company_visible(_as_uuid(company_id, "company_id"))
        if row is None:
            raise LookupError("Empresa não encontrada")
        self._assert_version(row, expected_updated_at)

        changes: dict[str, Any] = {}
        limits = {
            "company_name": 255, "name": 255, "website": 255, "phone": 50,
            "address": 500, "city": 100, "state": 100, "country": 100,
            "category": 100, "company_linkedin_url": 255, "instagram_url": 255,
        }
        for field, raw in values.items():
            value = _clean_optional(raw, limits[field])
            if field == "company_name" and not value:
                raise CrmEntityValidation("company_name não pode ficar vazio")
            old = getattr(row, field)
            if old == value:
                continue
            setattr(row, field, value)
            changes[field] = {"from": _json_value(old), "to": _json_value(value)}
            if field == "website":
                domain = normalize_domain(value)
                if row.normalized_domain != domain:
                    changes["normalized_domain"] = {"from": row.normalized_domain, "to": domain}
                    row.normalized_domain = domain
        if not changes:
            return row
        row.updated_at = datetime.now(timezone.utc)
        self._audit("company", row.id, changes)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_person(self, person_id: Any, *, expected_updated_at: Any, values: dict[str, Any]) -> Person:
        self._assert_write_role()
        unknown = sorted(set(values) - self.PERSON_FIELDS)
        if unknown:
            raise CrmEntityValidation("Campo(s) não editável(is): " + ", ".join(unknown))
        if not values:
            raise CrmEntityValidation("Informe ao menos um campo para atualizar")
        row = self._person_visible(_as_uuid(person_id, "person_id"))
        if row is None:
            raise LookupError("Pessoa não encontrada")
        self._assert_version(row, expected_updated_at)

        changes: dict[str, Any] = {}
        limits = {
            "name": 255, "role_label": 100, "email": 255, "phone": 50,
            "linkedin_url": 255, "verification_status": 40,
            "routability_type": 24, "routability_reason": 80,
        }
        for field, raw in values.items():
            if field == "routable":
                if not isinstance(raw, bool):
                    raise CrmEntityValidation("routable deve ser booleano")
                value = raw
            elif field == "role":
                if raw in (None, ""):
                    value = None
                else:
                    try:
                        value = ContactRole(str(raw))
                    except ValueError as exc:
                        raise CrmEntityValidation("role inválido") from exc
            else:
                value = _clean_optional(raw, limits[field])
            if field == "name" and not value:
                raise CrmEntityValidation("name não pode ficar vazio")
            old = getattr(row, field)
            if _json_value(old) == _json_value(value):
                continue
            setattr(row, field, value)
            changes[field] = {"from": _json_value(old), "to": _json_value(value)}
        if not changes:
            return row
        row.updated_at = datetime.now(timezone.utc)
        self._audit("person", row.id, changes)
        self.db.commit()
        self.db.refresh(row)
        return row

    def human_verify_person(self, person_id: Any, *, expected_updated_at: Any) -> Person:
        self._assert_write_role()
        row = self._person_visible(_as_uuid(person_id, "person_id"))
        if row is None:
            raise LookupError("Pessoa não encontrada")
        self._assert_version(row, expected_updated_at)
        now = datetime.now(timezone.utc)
        changes = {
            "verification_status": {"from": row.verification_status, "to": "human_verified"},
            "last_verified_at": {"from": _json_value(row.last_verified_at), "to": now.isoformat()},
        }
        row.verification_status = "human_verified"
        row.last_verified_at = now
        row.updated_at = now
        self._audit("person", row.id, changes)
        self.db.commit()
        self.db.refresh(row)
        return row
