"""Workflow Engine determinístico e tenant-aware para automação comercial segura."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from src.db.models import Lead
from database.commercial_intelligence_models import ProspectingAlert
from database.engagement_models import CommercialTask, WorkflowDefinition, WorkflowRun
from src.services.engagement_service import SequenceService

TRIGGERS = {
    "LEAD_CREATED",
    "LEAD_SCORED",
    "INTENT_DETECTED",
    "EVENT_DETECTED",
    "CONTACT_FOUND",
    "EMAIL_VERIFIED",
    "REPLY_RECEIVED",
    "MEETING_SCHEDULED",
    "WON",
    "DATA_STALE",
    "SAVED_SEARCH_MATCH",
}

CONDITION_FIELDS = {
    "offer_key",
    "score",
    "intent",
    "company_size",
    "persona",
    "contactability",
    "location",
    "provider",
    "channel",
    "lead_id",
}
CONDITION_OPERATORS = {"eq", "neq", "in", "gte", "lte", "exists"}
ACTION_TYPES = {
    "CREATE_TASK",
    "ENROLL_SEQUENCE",
    "NOTIFY",
    "ENRICH",
    "RERANK",
    "WEBHOOK",
    "CRM_SYNC",
}


def validate_workflow(
    trigger_type: str,
    conditions: list[dict[str, Any]],
    actions: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    trigger = str(trigger_type or "").strip().upper()
    if trigger not in TRIGGERS:
        raise ValueError("Trigger de workflow não suportado")
    if not isinstance(conditions, list) or len(conditions) > 20:
        raise ValueError("O workflow aceita no máximo 20 condições")
    if not isinstance(actions, list) or not 1 <= len(actions) <= 20:
        raise ValueError("O workflow precisa ter entre 1 e 20 ações")

    clean_conditions: list[dict[str, Any]] = []
    for raw in conditions:
        if not isinstance(raw, dict):
            raise ValueError("Condição inválida")
        field = str(raw.get("field") or "")
        operator = str(raw.get("operator") or "eq")
        if field not in CONDITION_FIELDS:
            raise ValueError(f"Campo de condição não permitido: {field or 'vazio'}")
        if operator not in CONDITION_OPERATORS:
            raise ValueError("Operador de condição não permitido")
        clean_conditions.append({"field": field, "operator": operator, "value": raw.get("value")})

    clean_actions: list[dict[str, Any]] = []
    for raw in actions:
        if not isinstance(raw, dict):
            raise ValueError("Ação inválida")
        action_type = str(raw.get("type") or "").strip().upper()
        if action_type not in ACTION_TYPES:
            raise ValueError(f"Ação não suportada: {action_type or 'vazia'}")
        config = raw.get("config") if isinstance(raw.get("config"), dict) else {}
        clean_actions.append({"type": action_type, "config": config})
    return trigger, clean_conditions, clean_actions


class WorkflowService:
    def __init__(self, db: Session, organization_id):
        self.db = db
        self.organization_id = organization_id

    def create_definition(
        self,
        *,
        name: str,
        trigger_type: str,
        conditions: list[dict[str, Any]],
        actions: list[dict[str, Any]],
        created_by_id=None,
        description: str | None = None,
    ) -> WorkflowDefinition:
        trigger, clean_conditions, clean_actions = validate_workflow(
            trigger_type,
            conditions,
            actions,
        )
        latest = (
            self.db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.organization_id == self.organization_id,
                WorkflowDefinition.name == name.strip(),
            )
            .order_by(WorkflowDefinition.version.desc())
            .first()
        )
        version = int(latest.version) + 1 if latest else 1
        row = WorkflowDefinition(
            organization_id=self.organization_id,
            name=name.strip(),
            description=description.strip() if description else None,
            trigger_type=trigger,
            conditions=clean_conditions,
            actions=clean_actions,
            version=version,
            created_by_id=created_by_id,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_definitions(self) -> list[WorkflowDefinition]:
        return (
            self.db.query(WorkflowDefinition)
            .filter(WorkflowDefinition.organization_id == self.organization_id)
            .order_by(WorkflowDefinition.name.asc(), WorkflowDefinition.version.desc())
            .all()
        )

    def run_event(
        self,
        *,
        trigger_type: str,
        event_key: str,
        context: dict[str, Any],
        webhook_dispatcher: Callable[[str, dict[str, Any]], bool] | None = None,
    ) -> list[WorkflowRun]:
        trigger = str(trigger_type or "").strip().upper()
        if trigger not in TRIGGERS:
            raise ValueError("Trigger de workflow não suportado")
        if not event_key or len(event_key) > 160:
            raise ValueError("event_key inválido")
        if not isinstance(context, dict):
            raise ValueError("context deve ser objeto")

        definitions = self.db.query(WorkflowDefinition).filter(
            WorkflowDefinition.organization_id == self.organization_id,
            WorkflowDefinition.trigger_type == trigger,
            WorkflowDefinition.enabled.is_(True),
        ).all()
        runs: list[WorkflowRun] = []
        for definition in definitions:
            existing = self.db.query(WorkflowRun).filter(
                WorkflowRun.organization_id == self.organization_id,
                WorkflowRun.workflow_id == definition.id,
                WorkflowRun.event_key == event_key,
            ).first()
            if existing:
                runs.append(existing)
                continue

            run = WorkflowRun(
                organization_id=self.organization_id,
                workflow_id=definition.id,
                trigger_type=trigger,
                event_key=event_key,
                entity_type=str(context.get("entity_type") or "")[:32] or None,
                entity_id=str(context.get("entity_id") or context.get("lead_id") or "")[:80] or None,
                context=context,
                status="RUNNING",
            )
            self.db.add(run)
            self.db.flush()

            if not self._conditions_match(definition.conditions or [], context):
                run.status = "SKIPPED"
                run.completed_at = datetime.now(timezone.utc)
                run.action_results = []
                runs.append(run)
                continue

            results: list[dict[str, Any]] = []
            try:
                for index, action in enumerate(definition.actions or []):
                    results.append(
                        self._execute_action(
                            run,
                            index,
                            action,
                            context,
                            webhook_dispatcher,
                        )
                    )
                run.status = "COMPLETED"
                run.completed_at = datetime.now(timezone.utc)
            except Exception as exc:
                run.status = "FAILED"
                run.error_message = str(exc)[:2000]
                run.completed_at = datetime.now(timezone.utc)
            run.action_results = results
            runs.append(run)
        self.db.commit()
        return runs

    def _execute_action(
        self,
        run: WorkflowRun,
        index: int,
        action: dict[str, Any],
        context: dict[str, Any],
        webhook_dispatcher: Callable[[str, dict[str, Any]], bool] | None,
    ) -> dict[str, Any]:
        action_type = str(action.get("type") or "").upper()
        config = action.get("config") if isinstance(action.get("config"), dict) else {}
        lead = self._tenant_lead(context.get("lead_id")) if context.get("lead_id") else None
        idempotency_key = f"workflow:{run.id}:{index}"

        if action_type == "CREATE_TASK":
            if not lead:
                raise ValueError("CREATE_TASK requer lead_id tenant-aware")
            task = self._task(
                lead=lead,
                idempotency_key=idempotency_key,
                task_type=str(config.get("task_type") or "RESEARCH")[:32],
                title=str(config.get("title") or "Executar ação comercial")[:180],
                description=str(config.get("description") or "")[:4000] or None,
                run=run,
            )
            return {"type": action_type, "status": "ok", "task_id": str(task.id)}

        if action_type == "ENROLL_SEQUENCE":
            if not lead or not config.get("sequence_id"):
                raise ValueError("ENROLL_SEQUENCE requer lead_id e sequence_id")
            enrollment = SequenceService(self.db, self.organization_id).enroll(
                sequence_id=config["sequence_id"],
                lead_id=lead.id,
                person_id=config.get("person_id"),
                enrolled_by_id=getattr(lead, "assigned_to_id", None),
            )
            return {
                "type": action_type,
                "status": "ok",
                "enrollment_id": str(enrollment.id),
            }

        if action_type == "NOTIFY":
            if not lead:
                raise ValueError("NOTIFY requer lead_id")
            fingerprint = f"workflow:{run.id}:{index}"
            alert = self.db.query(ProspectingAlert).filter(
                ProspectingAlert.organization_id == self.organization_id,
                ProspectingAlert.fingerprint == fingerprint,
            ).first()
            if not alert:
                alert = ProspectingAlert(
                    organization_id=self.organization_id,
                    lead_id=lead.id,
                    kind="workflow",
                    title=str(config.get("title") or "Ação comercial sugerida")[:255],
                    reason=str(config.get("message") or "Workflow comercial acionado")[:2000],
                    evidence={"workflow_run_id": str(run.id)},
                    fingerprint=fingerprint,
                )
                self.db.add(alert)
                self.db.flush()
            return {"type": action_type, "status": "ok", "alert_id": str(alert.id)}

        if action_type in {"ENRICH", "RERANK"}:
            if not lead:
                raise ValueError(f"{action_type} requer lead_id")
            # O pipeline legado reanalisa campanhas em lote e ainda não possui
            # um contrato de job por lead. Enfileirar max_leads=1 aqui poderia
            # atualizar OUTRO lead da campanha. Até existir targeting canônico,
            # materializamos uma tarefa explícita em vez de declarar sucesso
            # para uma automação semanticamente incorreta.
            task = self._task(
                lead=lead,
                idempotency_key=idempotency_key,
                task_type="DATA_ENRICHMENT" if action_type == "ENRICH" else "RERANK",
                title=(
                    "Atualizar dados desta oportunidade"
                    if action_type == "ENRICH"
                    else "Reavaliar prioridade desta oportunidade"
                ),
                description=(
                    "A atualização deve permanecer vinculada a este lead; "
                    "o job em lote não é usado para evitar reprocessar outra oportunidade."
                ),
                run=run,
                metadata={"requested_action": action_type},
            )
            return {
                "type": action_type,
                "status": "manual_required",
                "task_id": str(task.id),
            }

        if action_type == "WEBHOOK":
            if webhook_dispatcher is None:
                return {"type": action_type, "status": "not_dispatched"}
            sent = webhook_dispatcher(
                "workflow.triggered",
                {
                    "workflow_run_id": str(run.id),
                    "trigger_type": run.trigger_type,
                    "context": context,
                },
            )
            return {
                "type": action_type,
                "status": "queued" if sent else "disabled",
            }

        if action_type == "CRM_SYNC":
            if not lead:
                raise ValueError("CRM_SYNC requer lead_id")
            task = self._task(
                lead=lead,
                idempotency_key=idempotency_key,
                task_type="CRM_SYNC",
                title="Sincronizar oportunidade com CRM",
                description=(
                    "A integração externa depende de um adapter CRM configurado "
                    "para o workspace."
                ),
                run=run,
                metadata={"provider": config.get("provider")},
            )
            return {
                "type": action_type,
                "status": "manual_required",
                "task_id": str(task.id),
            }

        raise ValueError("Ação de workflow não suportada")

    def _task(
        self,
        *,
        lead: Lead,
        idempotency_key: str,
        task_type: str,
        title: str,
        description: str | None,
        run: WorkflowRun,
        metadata: dict[str, Any] | None = None,
    ) -> CommercialTask:
        task = self.db.query(CommercialTask).filter(
            CommercialTask.organization_id == self.organization_id,
            CommercialTask.idempotency_key == idempotency_key,
        ).first()
        if task:
            return task
        task = CommercialTask(
            organization_id=self.organization_id,
            lead_id=lead.id,
            owner_user_id=getattr(lead, "assigned_to_id", None),
            task_type=task_type,
            title=title,
            description=description,
            source="workflow",
            source_ref=str(run.id),
            idempotency_key=idempotency_key,
            task_metadata={"workflow_run_id": str(run.id), **(metadata or {})},
        )
        self.db.add(task)
        self.db.flush()
        return task

    def _tenant_lead(self, lead_id):
        lead = self.db.query(Lead).filter(
            Lead.id == lead_id,
            Lead.organization_id == self.organization_id,
        ).first()
        if not lead:
            raise LookupError("Lead não encontrado")
        return lead

    @staticmethod
    def _conditions_match(
        conditions: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> bool:
        for condition in conditions:
            actual = context.get(condition.get("field"))
            expected = condition.get("value")
            operator = condition.get("operator", "eq")
            if operator == "exists":
                if bool(actual is not None) != bool(
                    expected if expected is not None else True
                ):
                    return False
            elif operator == "eq" and actual != expected:
                return False
            elif operator == "neq" and actual == expected:
                return False
            elif operator == "in":
                values = expected if isinstance(expected, list) else [expected]
                if actual not in values:
                    return False
            elif operator in {"gte", "lte"}:
                if actual is None:
                    return False
                try:
                    left, right = float(actual), float(expected)
                except (TypeError, ValueError):
                    return False
                if operator == "gte" and left < right:
                    return False
                if operator == "lte" and left > right:
                    return False
        return True
