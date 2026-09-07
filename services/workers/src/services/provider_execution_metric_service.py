"""Persistência e agregação de execuções de providers externos."""
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import ProviderExecutionMetric


class ProviderExecutionMetricService:
    """Registra telemetria de providers separada do controle de quota."""

    def record(
        self,
        db: Session,
        organization_id: UUID,
        provider: str,
        status: str,
        *,
        job_id: Optional[UUID] = None,
        result_count: int = 0,
        duration_ms: int = 0,
        budget_used: int = 0,
        error_code: Optional[str] = None,
        retryable: bool = False,
        cost: Optional[float] = None,
    ) -> ProviderExecutionMetric:
        """Persiste uma medição de execução e devolve a entidade criada."""
        row = ProviderExecutionMetric(
            organization_id=organization_id,
            job_id=job_id,
            provider=provider,
            status=status,
            result_count=max(0, int(result_count)),
            duration_ms=max(0, int(duration_ms)),
            budget_used=max(0, int(budget_used)),
            error_code=error_code,
            retryable=bool(retryable),
            cost=cost,
            recorded_at=datetime.now(timezone.utc),
        )
        db.add(row)
        return row

    def list_for_organization(
        self,
        db: Session,
        organization_id: UUID,
        *,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        provider: Optional[str] = None,
    ) -> List[ProviderExecutionMetric]:
        """Lista medições org-scoped, com período e provider opcionais."""
        query = select(ProviderExecutionMetric).where(
            ProviderExecutionMetric.organization_id == organization_id,
        )
        if date_from:
            query = query.where(ProviderExecutionMetric.recorded_at >= date_from)
        if date_to:
            query = query.where(ProviderExecutionMetric.recorded_at <= date_to)
        if provider:
            query = query.where(ProviderExecutionMetric.provider == provider)
        return list(db.scalars(query.order_by(ProviderExecutionMetric.recorded_at.asc())).all())

    @staticmethod
    def aggregate_metrics(metrics: Iterable[Any]) -> Dict[str, Dict[str, Any]]:
        """Agrega medições por provider, distinguindo sucesso, vazio e falha."""
        buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "executions": 0,
            "successes": 0,
            "empty": 0,
            "failures": 0,
            "skipped": 0,
            "result_count": 0,
            "duration_total_ms": 0,
            "budget_used": 0,
            "cost": 0.0,
        })
        for item in metrics:
            provider = item.get("provider") if isinstance(item, dict) else item.provider
            status = item.get("status") if isinstance(item, dict) else item.status
            result_count = item.get("result_count", 0) if isinstance(item, dict) else item.result_count
            duration_ms = item.get("duration_ms", 0) if isinstance(item, dict) else item.duration_ms
            budget_used = item.get("budget_used", 0) if isinstance(item, dict) else item.budget_used
            cost = item.get("cost") if isinstance(item, dict) else item.cost
            bucket = buckets[provider]
            bucket["executions"] += 1
            bucket["successes"] += status in ("success", "ok")
            bucket["empty"] += status == "empty"
            bucket["failures"] += status == "failed"
            bucket["skipped"] += status in ("skipped", "disabled", "quota_exceeded")
            bucket["result_count"] += int(result_count or 0)
            bucket["duration_total_ms"] += int(duration_ms or 0)
            bucket["budget_used"] += int(budget_used or 0)
            bucket["cost"] += float(cost or 0)
        for bucket in buckets.values():
            total = bucket["executions"]
            bucket["average_duration_ms"] = round(bucket["duration_total_ms"] / total) if total else 0
            bucket["failure_rate"] = round(bucket["failures"] / total * 100, 1) if total else 0
            bucket["empty_rate"] = round(bucket["empty"] / total * 100, 1) if total else 0
            bucket["success_rate"] = round(bucket["successes"] / total * 100, 1) if total else 0
            bucket.pop("duration_total_ms")
            bucket["cost"] = round(bucket["cost"], 6)
        return dict(buckets)