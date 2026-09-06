"""Comparação A/B estatística persistida e aprovação auditável."""
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import CommercialComparison, CommercialOutcomeRow, OrgAuditEvent, User
from services.prospecting.learning_metrics import OutcomesRegistry, VersionComparator
from src.services.org_audit_service import log_org_event


class CommercialComparisonService:
    """Converte outcomes persistidos para o comparador estatístico existente."""

    def compute(
        self,
        db: Session,
        organization_id: UUID,
        offer_key: str,
        version_a: str,
        version_b: str,
        min_samples: int = 5,
    ) -> dict[str, Any]:
        rows = db.scalars(select(CommercialOutcomeRow).where(
            CommercialOutcomeRow.organization_id == organization_id,
            CommercialOutcomeRow.offer_key == offer_key,
        )).all()
        registry = OutcomesRegistry()
        for row in rows:
            registry.record(
                org_id=str(organization_id),
                offer_key=row.offer_key,
                outcome=row.outcome,
                lead_id=str(row.lead_id),
                value=float(row.value or 0),
                provider=row.provider,
                offer_version=row.offer_version,
            )
        return VersionComparator(registry, min_samples=min_samples).compare(
            offer_key, version_a, version_b,
        )

    def compute_and_persist(
        self,
        db: Session,
        organization_id: UUID,
        offer_key: str,
        version_a: str,
        version_b: str,
        min_samples: int = 5,
    ) -> CommercialComparison:
        result = self.compute(db, organization_id, offer_key, version_a, version_b, min_samples)
        comparison = CommercialComparison(
            organization_id=organization_id,
            offer_key=offer_key,
            version_a=version_a,
            version_b=version_b,
            result=result,
        )
        db.add(comparison)
        db.flush()
        return comparison

    def approve(
        self,
        db: Session,
        organization_id: UUID,
        comparison_id: UUID,
        approved_version: str,
        actor: User,
        evidence: str,
    ) -> CommercialComparison:
        comparison = db.scalars(select(CommercialComparison).where(
            CommercialComparison.id == comparison_id,
            CommercialComparison.organization_id == organization_id,
        )).first()
        if comparison is None:
            raise ValueError("Comparação não encontrada nesta organização")
        result = comparison.result or {}
        if approved_version not in (comparison.version_a, comparison.version_b):
            raise ValueError("A versão aprovada precisa pertencer à comparação")
        if result.get("recommendation") is None or result.get("verdict") != (
            "v1" if approved_version == comparison.version_a else "v2"
        ):
            raise ValueError("Somente uma recomendação estatisticamente conclusiva pode ser aprovada")
        comparison.approved_version = approved_version
        comparison.approved_by_id = actor.id
        comparison.approved_at = datetime.now(timezone.utc)
        comparison.approval_evidence = evidence.strip()
        log_org_event(
            db,
            organization_id,
            OrgAuditEvent.AB_COMPARISON_APPROVED,
            actor=actor,
            target_type="commercial_comparison",
            target_id=str(comparison.id),
            detail=f"versao={approved_version}; evidencia={evidence.strip()[:500]}",
        )
        return comparison