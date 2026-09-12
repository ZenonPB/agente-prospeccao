"""Sequence Engine v2 e decisões persistidas de próxima ação.

O motor materializa ações humanas como tarefas. Envios automáticos continuam
sob a cadência existente e seus gates de opt-in/verificação; este módulo não
cria um segundo caminho de SMTP.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.db.models import Lead, LeadOpportunityRow, Person
from database.engagement_models import (
    CommercialTask,
    NextBestActionDecision,
    SequenceEnrollment,
    SequenceExecution,
    SequenceTemplate,
)
from services.prospecting.next_best_action_service import NextBestActionService

STEP_TYPES = {"EMAIL", "CALL", "LINKEDIN", "WHATSAPP", "RESEARCH", "WAIT", "CONDITION"}
TASK_STEP_TYPES = {"EMAIL", "CALL", "LINKEDIN", "WHATSAPP", "RESEARCH"}
ENROLLMENT_ACTIVE = {"ACTIVE", "PAUSED"}


def validate_sequence_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(steps, list) or not 1 <= len(steps) <= 30:
        raise ValueError("A sequência precisa ter entre 1 e 30 etapas")

    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(steps):
        if not isinstance(raw, dict):
            raise ValueError(f"Etapa {index + 1} inválida")
        step_type = str(raw.get("type") or "").strip().upper()
        if step_type not in STEP_TYPES:
            raise ValueError(f"Tipo de etapa inválido: {step_type or 'vazio'}")
        delay = raw.get("delay_minutes", 0)
        if isinstance(delay, bool) or not isinstance(delay, int) or not 0 <= delay <= 525_600:
            raise ValueError("delay_minutes deve ser inteiro entre 0 e 525600")
        clean = {
            "type": step_type,
            "delay_minutes": delay,
            "title": str(raw.get("title") or "").strip()[:180],
            "description": str(raw.get("description") or "").strip()[:4000],
            "config": raw.get("config") if isinstance(raw.get("config"), dict) else {},
        }
        if step_type == "EMAIL":
            clean["subject"] = str(raw.get("subject") or "").strip()[:255]
            clean["content"] = str(raw.get("content") or "").strip()[:10_000]
        if step_type == "CONDITION":
            config = clean["config"]
            field = str(config.get("field") or "")
            operator = str(config.get("operator") or "eq")
            if field not in {"lead.status", "lead.score", "lead.opt_out"}:
                raise ValueError("Condição usa campo não permitido")
            if operator not in {"eq", "neq", "gte", "lte"}:
                raise ValueError("Operador de condição não permitido")
            if str(config.get("on_false") or "skip") not in {"skip", "stop"}:
                raise ValueError("on_false deve ser skip ou stop")
        normalized.append(clean)
    return normalized


class SequenceService:
    def __init__(self, db: Session, organization_id):
        self.db = db
        self.organization_id = organization_id

    def create_template(
        self,
        *,
        name: str,
        steps: list[dict[str, Any]],
        created_by_id=None,
        description: str | None = None,
        offer_key: str | None = None,
        persona_key: str | None = None,
    ) -> SequenceTemplate:
        clean_steps = validate_sequence_steps(steps)
        latest = (
            self.db.query(SequenceTemplate)
            .filter(
                SequenceTemplate.organization_id == self.organization_id,
                SequenceTemplate.name == name.strip(),
            )
            .order_by(SequenceTemplate.version.desc())
            .first()
        )
        version = int(latest.version) + 1 if latest else 1
        row = SequenceTemplate(
            organization_id=self.organization_id,
            name=name.strip(),
            description=description.strip() if description else None,
            offer_key=offer_key.strip() if offer_key else None,
            persona_key=persona_key.strip() if persona_key else None,
            version=version,
            steps=clean_steps,
            created_by_id=created_by_id,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_templates(self) -> list[SequenceTemplate]:
        return (
            self.db.query(SequenceTemplate)
            .filter(SequenceTemplate.organization_id == self.organization_id)
            .order_by(SequenceTemplate.name.asc(), SequenceTemplate.version.desc())
            .all()
        )

    def enroll(self, *, sequence_id, lead_id, person_id=None, enrolled_by_id=None) -> SequenceEnrollment:
        template = self.db.query(SequenceTemplate).filter(
            SequenceTemplate.id == sequence_id,
            SequenceTemplate.organization_id == self.organization_id,
            SequenceTemplate.enabled.is_(True),
        ).first()
        if not template:
            raise LookupError("Sequência não encontrada")

        lead = self.db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.organization_id == self.organization_id,
        ).first()
        if not lead:
            raise LookupError("Lead não encontrado")
        if lead.opt_out:
            raise ValueError("Lead opt-out não pode entrar em sequência")

        if person_id:
            person = self.db.query(Person).filter(
                Person.id == person_id,
                Person.organization_id == self.organization_id,
            ).first()
            if not person:
                raise LookupError("Pessoa não encontrada")

        existing = self.db.query(SequenceEnrollment).filter(
            SequenceEnrollment.sequence_id == template.id,
            SequenceEnrollment.lead_id == lead.id,
            SequenceEnrollment.organization_id == self.organization_id,
        ).first()
        if existing:
            return existing

        now = datetime.now(timezone.utc)
        enrollment = SequenceEnrollment(
            organization_id=self.organization_id,
            sequence_id=template.id,
            lead_id=lead.id,
            person_id=person_id,
            enrolled_by_id=enrolled_by_id,
            status="ACTIVE",
            current_step_index=0,
        )
        self.db.add(enrollment)
        self.db.flush()

        scheduled = now
        for index, step in enumerate(template.steps or []):
            scheduled += timedelta(minutes=int(step.get("delay_minutes") or 0))
            self.db.add(SequenceExecution(
                organization_id=self.organization_id,
                enrollment_id=enrollment.id,
                lead_id=lead.id,
                step_index=index,
                step_type=step["type"],
                scheduled_at=scheduled,
                payload=step,
                idempotency_key=f"sequence:{enrollment.id}:{index}",
            ))
        enrollment.next_action_at = now + timedelta(minutes=int((template.steps or [{}])[0].get("delay_minutes") or 0))
        self.db.commit()
        self.db.refresh(enrollment)
        return enrollment

    def list_enrollments(self, *, status: str | None = None, limit: int = 100) -> list[SequenceEnrollment]:
        query = self.db.query(SequenceEnrollment).filter(
            SequenceEnrollment.organization_id == self.organization_id,
        )
        if status:
            query = query.filter(SequenceEnrollment.status == status)
        return query.order_by(SequenceEnrollment.updated_at.desc()).limit(limit).all()

    def process_due(self, *, limit: int = 100) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        rows = (
            self.db.query(SequenceEnrollment)
            .filter(
                SequenceEnrollment.organization_id == self.organization_id,
                SequenceEnrollment.status == "ACTIVE",
                SequenceEnrollment.next_action_at.isnot(None),
                SequenceEnrollment.next_action_at <= now,
            )
            .order_by(SequenceEnrollment.next_action_at.asc())
            .limit(limit)
            .all()
        )
        stats = {"processed": 0, "tasks_created": 0, "completed": 0, "stopped": 0}
        for enrollment in rows:
            result = self._process_current(enrollment, now)
            stats["processed"] += 1
            stats[result] += 1
        self.db.commit()
        return stats

    def _process_current(self, enrollment: SequenceEnrollment, now: datetime) -> str:
        execution = self.db.query(SequenceExecution).filter(
            SequenceExecution.organization_id == self.organization_id,
            SequenceExecution.enrollment_id == enrollment.id,
            SequenceExecution.step_index == enrollment.current_step_index,
        ).first()
        if not execution:
            enrollment.status = "COMPLETED"
            enrollment.next_action_at = None
            return "completed"
        if execution.status in {"COMPLETED", "SKIPPED"}:
            self._advance(enrollment, now)
            return "completed" if enrollment.status == "COMPLETED" else "processed"
        if execution.status == "READY":
            return "processed"
        if execution.scheduled_at > now:
            enrollment.next_action_at = execution.scheduled_at
            return "processed"

        if execution.step_type == "WAIT":
            execution.status = "COMPLETED"
            execution.completed_at = now
            self._advance(enrollment, now)
            return "completed" if enrollment.status == "COMPLETED" else "processed"

        if execution.step_type == "CONDITION":
            if self._condition_matches(enrollment.lead_id, execution.payload.get("config") or {}):
                execution.status = "COMPLETED"
                execution.completed_at = now
                self._advance(enrollment, now)
                return "completed" if enrollment.status == "COMPLETED" else "processed"
            execution.status = "SKIPPED"
            execution.completed_at = now
            if str((execution.payload.get("config") or {}).get("on_false") or "skip") == "stop":
                enrollment.status = "STOPPED"
                enrollment.pause_reason = "CONDITION_NOT_MET"
                enrollment.next_action_at = None
                self._skip_remaining(enrollment.id, now)
                return "stopped"
            self._advance(enrollment, now)
            return "completed" if enrollment.status == "COMPLETED" else "processed"

        if execution.step_type in TASK_STEP_TYPES:
            task_key = f"sequence-task:{enrollment.id}:{execution.step_index}"
            task = self.db.query(CommercialTask).filter(
                CommercialTask.organization_id == self.organization_id,
                CommercialTask.idempotency_key == task_key,
            ).first()
            if not task:
                payload = execution.payload or {}
                title = payload.get("title") or self._default_task_title(execution.step_type)
                task = CommercialTask(
                    organization_id=self.organization_id,
                    lead_id=enrollment.lead_id,
                    person_id=enrollment.person_id,
                    enrollment_id=enrollment.id,
                    owner_user_id=enrollment.enrolled_by_id,
                    task_type=execution.step_type,
                    title=title,
                    description=payload.get("description") or payload.get("content"),
                    due_at=execution.scheduled_at,
                    source="sequence",
                    source_ref=str(execution.id),
                    idempotency_key=task_key,
                    task_metadata={
                        "subject": payload.get("subject"),
                        "content": payload.get("content"),
                        "sequence_step": execution.step_index,
                    },
                )
                self.db.add(task)
            execution.status = "READY"
            execution.ready_at = now
            enrollment.next_action_at = None
            return "tasks_created"

        execution.status = "SKIPPED"
        execution.completed_at = now
        self._advance(enrollment, now)
        return "processed"

    def complete_execution(self, *, execution_id, outcome: dict[str, Any] | None = None) -> SequenceExecution:
        execution = self.db.query(SequenceExecution).filter(
            SequenceExecution.id == execution_id,
            SequenceExecution.organization_id == self.organization_id,
        ).first()
        if not execution:
            raise LookupError("Etapa não encontrada")
        if execution.status in {"COMPLETED", "SKIPPED"}:
            return execution
        now = datetime.now(timezone.utc)
        execution.status = "COMPLETED"
        execution.completed_at = now
        execution.outcome = outcome or {}
        task = self.db.query(CommercialTask).filter(
            CommercialTask.organization_id == self.organization_id,
            CommercialTask.source_ref == str(execution.id),
            CommercialTask.status == "OPEN",
        ).first()
        if task:
            task.status = "COMPLETED"
            task.completed_at = now
        enrollment = self.db.query(SequenceEnrollment).filter(
            SequenceEnrollment.id == execution.enrollment_id,
            SequenceEnrollment.organization_id == self.organization_id,
        ).first()
        if enrollment and enrollment.status == "ACTIVE":
            self._advance(enrollment, now)
        self.db.commit()
        self.db.refresh(execution)
        return execution

    def pause_for_lead(self, lead_id, reason: str, *, terminal: bool = False) -> int:
        rows = self.db.query(SequenceEnrollment).filter(
            SequenceEnrollment.organization_id == self.organization_id,
            SequenceEnrollment.lead_id == lead_id,
            SequenceEnrollment.status.in_(["ACTIVE", "PAUSED"]),
        ).all()
        now = datetime.now(timezone.utc)
        for row in rows:
            row.status = "STOPPED" if terminal else "PAUSED"
            row.pause_reason = reason[:255]
            row.next_action_at = None
            if terminal:
                self._skip_remaining(row.id, now)
        return len(rows)

    def resume(self, enrollment_id) -> SequenceEnrollment:
        row = self.db.query(SequenceEnrollment).filter(
            SequenceEnrollment.id == enrollment_id,
            SequenceEnrollment.organization_id == self.organization_id,
        ).first()
        if not row:
            raise LookupError("Inscrição não encontrada")
        if row.status != "PAUSED":
            return row
        row.status = "ACTIVE"
        row.pause_reason = None
        current = self.db.query(SequenceExecution).filter(
            SequenceExecution.enrollment_id == row.id,
            SequenceExecution.step_index == row.current_step_index,
        ).first()
        row.next_action_at = current.scheduled_at if current and current.status == "PENDING" else datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return row

    def _advance(self, enrollment: SequenceEnrollment, now: datetime) -> None:
        enrollment.last_action_at = now
        enrollment.current_step_index += 1
        next_execution = self.db.query(SequenceExecution).filter(
            SequenceExecution.enrollment_id == enrollment.id,
            SequenceExecution.step_index == enrollment.current_step_index,
        ).first()
        if not next_execution:
            enrollment.status = "COMPLETED"
            enrollment.next_action_at = None
            return
        enrollment.next_action_at = next_execution.scheduled_at

    def _skip_remaining(self, enrollment_id, now: datetime) -> None:
        for execution in self.db.query(SequenceExecution).filter(
            SequenceExecution.enrollment_id == enrollment_id,
            SequenceExecution.status.in_(["PENDING", "READY"]),
        ).all():
            execution.status = "SKIPPED"
            execution.completed_at = now

    def _condition_matches(self, lead_id, config: dict[str, Any]) -> bool:
        lead = self.db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.organization_id == self.organization_id,
        ).first()
        if not lead:
            return False
        field = config.get("field")
        actual: Any
        if field == "lead.status":
            actual = getattr(getattr(lead, "status", None), "value", getattr(lead, "status", None))
        elif field == "lead.score":
            actual = getattr(lead, "score", None)
        elif field == "lead.opt_out":
            actual = bool(getattr(lead, "opt_out", False))
        else:
            return False
        expected = config.get("value")
        operator = config.get("operator", "eq")
        if operator == "eq":
            return actual == expected
        if operator == "neq":
            return actual != expected
        if actual is None:
            return False
        try:
            left, right = float(actual), float(expected)
        except (TypeError, ValueError):
            return False
        return left >= right if operator == "gte" else left <= right

    @staticmethod
    def _default_task_title(step_type: str) -> str:
        return {
            "EMAIL": "Enviar e-mail",
            "CALL": "Ligar para o contato",
            "LINKEDIN": "Abordar pelo LinkedIn",
            "WHATSAPP": "Abordar pelo WhatsApp",
            "RESEARCH": "Pesquisar antes do próximo contato",
        }.get(step_type, "Executar próxima ação")


class NextBestActionDecisionService:
    ACTION_MAP = {
        "START_EMAIL_CADENCE": "SEND_EMAIL",
        "REVIEW_DECISION_MAKER": "RESEARCH",
        "CALL": "CALL",
        "RESEARCH": "RESEARCH",
        "RE_ENRICH": "RE_ENRICH",
        "STOP": "STOP",
    }

    def __init__(self, db: Session, organization_id):
        self.db = db
        self.organization_id = organization_id

    def refresh(self, lead_id) -> NextBestActionDecision:
        lead = self.db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.organization_id == self.organization_id,
        ).first()
        if not lead:
            raise LookupError("Lead não encontrado")

        person = None
        if getattr(lead, "company_id", None):
            person = self.db.query(Person).filter(
                Person.organization_id == self.organization_id,
                Person.company_id == lead.company_id,
            ).order_by(Person.identity_confidence.desc()).first()
        opportunities = self.db.query(LeadOpportunityRow).filter(
            LeadOpportunityRow.organization_id == self.organization_id,
            LeadOpportunityRow.lead_id == lead.id,
        ).all()
        snapshot = {
            "status": getattr(getattr(lead, "status", None), "value", getattr(lead, "status", None)),
            "opt_out": bool(getattr(lead, "opt_out", False)),
            "has_verified_email": bool(person and person.email and person.email_verified),
            "email_verified": bool(person and person.email_verified),
            "verification_status": getattr(person, "verification_status", None) if person else None,
            "routability_type": getattr(person, "routability_type", None) if person else None,
            "routable": bool(getattr(person, "routable", False)) if person else False,
            "phone": getattr(person, "phone", None) if person else None,
            "has_contact": bool(person),
            "opportunities": [
                {
                    "offer_key": row.offer_key,
                    "score": float(row.score or 0),
                    "overall": float((row.opportunity_vector or {}).get("overall") or 0) if hasattr(row, "opportunity_vector") else 0,
                }
                for row in opportunities
            ],
        }
        recommendation = NextBestActionService().recommend(snapshot)
        action = self.ACTION_MAP.get(str(recommendation.get("action")), str(recommendation.get("action") or "RESEARCH"))
        payload = {
            "action": action,
            "why": recommendation.get("why"),
            "confidence": recommendation.get("confidence"),
            "evidence": recommendation.get("evidence") or [],
            "offer_key": recommendation.get("offer_key"),
            "lead_status": snapshot["status"],
            "verification_status": snapshot["verification_status"],
            "routability_type": snapshot["routability_type"],
        }
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        existing = self.db.query(NextBestActionDecision).filter(
            NextBestActionDecision.organization_id == self.organization_id,
            NextBestActionDecision.lead_id == lead.id,
            NextBestActionDecision.fingerprint == fingerprint,
        ).first()
        if existing:
            return existing

        confidence = float(recommendation.get("confidence") or 0)
        deadline = None if action == "STOP" else datetime.now(timezone.utc) + timedelta(days=1 if confidence >= 0.85 else 3)
        row = NextBestActionDecision(
            organization_id=self.organization_id,
            lead_id=lead.id,
            action=action,
            why=str(recommendation.get("why") or "next_best_action")[:255],
            confidence=confidence,
            evidence=recommendation.get("evidence") or [],
            deadline=deadline,
            offer_key=recommendation.get("offer_key"),
            fingerprint=fingerprint,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
