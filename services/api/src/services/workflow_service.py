"""Workflow Engine determinístico e tenant-aware para automação comercial segura."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from src.db.models import Lead, OrganizationMember
from database.commercial_intelligence_models import ProspectingAlert
from database.crm_models import ProspectList, ProspectListMember
from database.engagement_models import CommercialTask, WorkflowDefinition, WorkflowRun
from src.services.engagement_service import SequenceService

TRIGGERS = {
    "LEAD_CREATED", "LEAD_SCORED", "INTENT_DETECTED", "EVENT_DETECTED",
    "CONTACT_FOUND", "EMAIL_VERIFIED", "REPLY_RECEIVED", "MEETING_SCHEDULED",
    "WON", "DATA_STALE", "SAVED_SEARCH_MATCH",
}
CONDITION_FIELDS = {
    "offer_key", "score", "intent", "company_size", "persona", "contactability",
    "location", "provider", "channel", "lead_id",
}
CONDITION_OPERATORS = {"eq", "neq", "in", "gte", "lte", "exists"}
ACTION_TYPES = {
    "CREATE_TASK", "ENROLL_SEQUENCE", "NOTIFY", "ENRICH", "RERANK",
    "WEBHOOK", "CRM_SYNC", "ADD_TO_LIST", "ASSIGN_OWNER",
}


def validate_workflow(trigger_type: str, conditions: list[dict[str, Any]], actions: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
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

    def create_definition(self, *, name: str, trigger_type: str, conditions: list[dict[str, Any]], actions: list[dict[str, Any]], created_by_id=None, description: str | None = None) -> WorkflowDefinition:
        trigger, clean_conditions, clean_actions = validate_workflow(trigger_type, conditions, actions)
        latest = self.db.query(WorkflowDefinition).filter(
            WorkflowDefinition.organization_id == self.organization_id,
            WorkflowDefinition.name == name.strip(),
        ).order_by(WorkflowDefinition.version.desc()).first()
        row = WorkflowDefinition(
            organization_id=self.organization_id,
            name=name.strip(),
            description=description.strip() if description else None,
            trigger_type=trigger,
            conditions=clean_conditions,
            actions=clean_actions,
            version=int(latest.version) + 1 if latest else 1,
            created_by_id=created_by_id,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_definitions(self) -> list[WorkflowDefinition]:
        return self.db.query(WorkflowDefinition).filter(
            WorkflowDefinition.organization_id == self.organization_id,
        ).order_by(WorkflowDefinition.name.asc(), WorkflowDefinition.version.desc()).all()

    def run_event(self, *, trigger_type: str, event_key: str, context: dict[str, Any], webhook_dispatcher: Callable[[str, dict[str, Any]], bool] | None = None) -> list[WorkflowRun]:
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
                    results.append(self._execute_action(run, index, action, context, webhook_dispatcher))
                run.status = "COMPLETED"
            except Exception as exc:
                run.status = "FAILED"
                run.error_message = str(exc)[:2000]
            run.completed_at = datetime.now(timezone.utc)
            run.action_results = results
            runs.append(run)
        self.db.commit()
        return runs

    def _execute_action(self, run: WorkflowRun, index: int, action: dict[str, Any], context: dict[str, Any], webhook_dispatcher: Callable[[str, dict[str, Any]], bool] | None) -> dict[str, Any]:
        action_type = str(action.get("type") or "").upper()
        config = action.get("config") if isinstance(action.get("config"), dict) else {}
        lead = self._tenant_lead(context.get("lead_id")) if context.get("lead_id") else None
        key = f"workflow:{run.id}:{index}"
        if action_type == "CREATE_TASK":
            if not lead: raise ValueError("CREATE_TASK requer lead_id tenant-aware")
            task = self._task(lead, key, str(config.get("task_type") or "RESEARCH")[:32], str(config.get("title") or "Executar ação comercial")[:180], str(config.get("description") or "")[:4000] or None, run)
            return {"type": action_type, "status": "ok", "task_id": str(task.id)}
        if action_type == "ENROLL_SEQUENCE":
            if not lead or not config.get("sequence_id"): raise ValueError("ENROLL_SEQUENCE requer lead_id e sequence_id")
            enrollment = SequenceService(self.db, self.organization_id).enroll(sequence_id=config["sequence_id"], lead_id=lead.id, person_id=config.get("person_id"), enrolled_by_id=getattr(lead, "assigned_to_id", None))
            return {"type": action_type, "status": "ok", "enrollment_id": str(enrollment.id)}
        if action_type == "NOTIFY":
            if not lead: raise ValueError("NOTIFY requer lead_id")
            alert = self.db.query(ProspectingAlert).filter(ProspectingAlert.organization_id == self.organization_id, ProspectingAlert.fingerprint == key).first()
            if not alert:
                alert = ProspectingAlert(organization_id=self.organization_id, lead_id=lead.id, kind="workflow", title=str(config.get("title") or "Ação comercial sugerida")[:255], reason=str(config.get("message") or "Automação comercial acionada")[:2000], evidence={"workflow_run_id": str(run.id)}, fingerprint=key)
                self.db.add(alert); self.db.flush()
            return {"type": action_type, "status": "ok", "alert_id": str(alert.id)}
        if action_type == "ADD_TO_LIST":
            if not lead or not config.get("list_id"): raise ValueError("ADD_TO_LIST requer lead_id e list_id")
            prospect_list = self.db.query(ProspectList).filter(ProspectList.id == config["list_id"], ProspectList.organization_id == self.organization_id, ProspectList.active.is_(True)).first()
            if not prospect_list: raise LookupError("Lista não encontrada")
            member = self.db.query(ProspectListMember).filter(ProspectListMember.list_id == prospect_list.id, ProspectListMember.lead_id == lead.id).first()
            if not member:
                member = ProspectListMember(organization_id=self.organization_id, list_id=prospect_list.id, lead_id=lead.id, source="workflow", source_ref=str(run.id))
                self.db.add(member); self.db.flush()
            return {"type": action_type, "status": "ok", "list_id": str(prospect_list.id)}
        if action_type == "ASSIGN_OWNER":
            if not lead or not config.get("user_id"): raise ValueError("ASSIGN_OWNER requer lead_id e user_id")
            member = self.db.query(OrganizationMember).filter(OrganizationMember.organization_id == self.organization_id, OrganizationMember.user_id == config["user_id"]).first()
            if not member: raise LookupError("Responsável não pertence a este espaço de trabalho")
            lead.assigned_to_id = member.user_id
            self.db.add(lead); self.db.flush()
            return {"type": action_type, "status": "ok", "owner_user_id": str(member.user_id)}
        if action_type in {"ENRICH", "RERANK"}:
            if not lead: raise ValueError(f"{action_type} requer lead_id")
            task = self._task(lead, key, "DATA_ENRICHMENT" if action_type == "ENRICH" else "RERANK", "Atualizar dados desta oportunidade" if action_type == "ENRICH" else "Reavaliar prioridade desta oportunidade", "A atualização permanece vinculada a este lead; o processamento em lote não é usado para evitar alterar outra oportunidade.", run, {"requested_action": action_type})
            return {"type": action_type, "status": "manual_required", "task_id": str(task.id)}
        if action_type == "WEBHOOK":
            if webhook_dispatcher is None: return {"type": action_type, "status": "not_dispatched"}
            sent = webhook_dispatcher("workflow.triggered", {"workflow_run_id": str(run.id), "trigger_type": run.trigger_type, "context": context})
            return {"type": action_type, "status": "queued" if sent else "disabled"}
        if action_type == "CRM_SYNC":
            if not lead: raise ValueError("CRM_SYNC requer lead_id")
            # A chamada externa permanece fora da transação síncrona do workflow.
            # A tarefa aponta para a integração configurada e pode ser processada
            # pela API/scheduler sem manter locks enquanto aguarda rede.
            task = self._task(lead, key, "CRM_SYNC", "Sincronizar com o sistema comercial", "Sincronização pendente para execução pelo conector configurado.", run, {"provider": config.get("provider"), "connection_id": config.get("connection_id")})
            return {"type": action_type, "status": "queued_manual_gate", "task_id": str(task.id)}
        raise ValueError("Ação de workflow não suportada")

    def _task(self, lead: Lead, idempotency_key: str, task_type: str, title: str, description: str | None, run: WorkflowRun, metadata: dict[str, Any] | None = None) -> CommercialTask:
        task = self.db.query(CommercialTask).filter(CommercialTask.organization_id == self.organization_id, CommercialTask.idempotency_key == idempotency_key).first()
        if task: return task
        task = CommercialTask(organization_id=self.organization_id, lead_id=lead.id, owner_user_id=getattr(lead, "assigned_to_id", None), task_type=task_type, title=title, description=description, source="workflow", source_ref=str(run.id), idempotency_key=idempotency_key, task_metadata={"workflow_run_id": str(run.id), **(metadata or {})})
        self.db.add(task); self.db.flush(); return task

    def _tenant_lead(self, lead_id):
        lead = self.db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == self.organization_id).first()
        if not lead: raise LookupError("Lead não encontrado")
        return lead

    @staticmethod
    def _conditions_match(conditions: list[dict[str, Any]], context: dict[str, Any]) -> bool:
        for condition in conditions:
            actual, expected, operator = context.get(condition.get("field")), condition.get("value"), condition.get("operator", "eq")
            if operator == "exists" and bool(actual is not None) != bool(expected if expected is not None else True): return False
            if operator == "eq" and actual != expected: return False
            if operator == "neq" and actual == expected: return False
            if operator == "in" and actual not in (expected if isinstance(expected, list) else [expected]): return False
            if operator in {"gte", "lte"}:
                if actual is None: return False
                try: left, right = float(actual), float(expected)
                except (TypeError, ValueError): return False
                if operator == "gte" and left < right: return False
                if operator == "lte" and left > right: return False
        return True
