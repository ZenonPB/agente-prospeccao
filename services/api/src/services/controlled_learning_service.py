"""Learning comercial controlado com publicação e rollback auditáveis."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from src.db.models import ControlledLearningProposal

_EVIDENCE_FIELDS = frozenset({"verdict", "recommendation", "delta", "v1", "v2"})


def build_learning_proposal(comparison: Any) -> dict[str, Any]:
    approved_version = getattr(comparison, "approved_version", None)
    if not approved_version:
        raise ValueError("comparação ainda não foi aprovada")
    version_a = getattr(comparison, "version_a", None)
    version_b = getattr(comparison, "version_b", None)
    if approved_version not in (version_a, version_b):
        raise ValueError("versão aprovada não pertence à comparação")
    comparison_id = getattr(comparison, "id", None)
    offer_key = getattr(comparison, "offer_key", None)
    if not comparison_id or not offer_key:
        raise ValueError("comparação sem identidade ou oferta")
    result = getattr(comparison, "result", None)
    if not isinstance(result, dict):
        raise ValueError("comparação sem resultado estatístico")
    expected_verdict = "v1" if approved_version == version_a else "v2"
    recommendation = result.get("recommendation")
    if result.get("verdict") != expected_verdict or not isinstance(recommendation, str) or not recommendation.strip():
        raise ValueError("somente uma recomendação conclusiva pode gerar learning")
    return {
        "organization_id": getattr(comparison, "organization_id", None),
        "offer_key": offer_key,
        "source_comparison_id": str(comparison_id),
        "approved_version": approved_version,
        "approved_by_id": getattr(comparison, "approved_by_id", None),
        "status": "PROPOSED",
        "evidence_snapshot": {key: deepcopy(result[key]) for key in _EVIDENCE_FIELDS if key in result},
        "requires_manual_publication": True,
    }


class ControlledLearningService:
    """Fecha observe → recommend → approve → publish → rollback."""

    def create_from_comparison(self, db: Any, organization_id: UUID, comparison_id: UUID, actor: Any = None) -> ControlledLearningProposal:
        from sqlalchemy import func, select
        from src.db.models import CommercialComparison, ControlledLearningProposal, OrgAuditEvent
        from src.services.org_audit_service import log_org_event

        comparison = db.scalars(select(CommercialComparison).where(
            CommercialComparison.id == comparison_id,
            CommercialComparison.organization_id == organization_id,
        )).first()
        if comparison is None:
            raise ValueError("Comparação não encontrada nesta organização")
        existing = db.scalars(select(ControlledLearningProposal).where(
            ControlledLearningProposal.organization_id == organization_id,
            ControlledLearningProposal.source_comparison_id == comparison_id,
        )).first()
        if existing is not None:
            return existing
        payload = build_learning_proposal(comparison)
        latest = db.scalar(select(func.max(ControlledLearningProposal.proposal_version)).where(
            ControlledLearningProposal.organization_id == organization_id,
            ControlledLearningProposal.offer_key == comparison.offer_key,
        )) or 0
        proposal = ControlledLearningProposal(
            organization_id=organization_id,
            source_comparison_id=comparison.id,
            offer_key=payload["offer_key"],
            proposal_version=latest + 1,
            approved_version=payload["approved_version"],
            approved_by_id=payload["approved_by_id"],
            status=payload["status"],
            evidence_snapshot=payload["evidence_snapshot"],
        )
        db.add(proposal)
        db.flush()
        log_org_event(
            db, organization_id, OrgAuditEvent.CONTROLLED_LEARNING_PROPOSED,
            actor=actor, target_type="controlled_learning_proposal",
            target_id=str(proposal.id),
            detail=f"comparison={comparison.id}; offer={comparison.offer_key}; proposal_version={proposal.proposal_version}; status=PROPOSED",
        )
        return proposal

    def publish_profile(self, db: Any, organization_id: UUID, proposal_id: UUID, profile_snapshot: dict[str, Any], actor: Any) -> Any:
        """Publica exatamente a versão aprovada, com lock e snapshot imutável."""
        from sqlalchemy import select
        from database.learning_models import OfferProfileActivation, OfferProfileVersion
        from src.db.models import ControlledLearningProposal
        from services.prospecting.default_profiles import get_default_registry
        from services.prospecting.offer_profile import OfferProfile
        from services.prospecting.offer_profile_validator import validate_profile

        proposal = db.scalars(select(ControlledLearningProposal).where(
            ControlledLearningProposal.id == proposal_id,
            ControlledLearningProposal.organization_id == organization_id,
        ).with_for_update()).first()
        if proposal is None:
            raise ValueError("Proposta de learning não encontrada")
        if proposal.status == "PUBLISHED":
            existing = db.scalars(select(OfferProfileVersion).where(
                OfferProfileVersion.organization_id == organization_id,
                OfferProfileVersion.source_proposal_id == proposal.id,
            )).first()
            if existing is not None:
                return existing
        if proposal.status != "PROPOSED":
            raise ValueError("Proposta não está disponível para publicação")

        snapshot = deepcopy(profile_snapshot or {})
        if snapshot.get("key") != proposal.offer_key:
            raise ValueError("O OfferProfile não pertence à oferta aprovada")
        if snapshot.get("version") != proposal.approved_version:
            raise ValueError("A versão publicada deve ser exatamente a versão aprovada")
        profile = OfferProfile.from_dict(snapshot)
        errors = [item for item in validate_profile(profile) if not str(item).startswith("aviso:")]
        if errors:
            raise ValueError("OfferProfile inválido: " + "; ".join(errors))

        existing_version = db.scalars(select(OfferProfileVersion).where(
            OfferProfileVersion.organization_id == organization_id,
            OfferProfileVersion.offer_key == proposal.offer_key,
            OfferProfileVersion.version == profile.version,
        )).first()
        if existing_version is not None:
            raise ValueError("Esta versão de OfferProfile já existe")

        # Primeira publicação ganha um baseline persistido para rollback exato.
        any_version = db.scalars(select(OfferProfileVersion).where(
            OfferProfileVersion.organization_id == organization_id,
            OfferProfileVersion.offer_key == proposal.offer_key,
        ).limit(1)).first()
        if any_version is None:
            baseline = get_default_registry().get(proposal.offer_key)
            if baseline is None:
                raise ValueError("Oferta base não existe no catálogo")
            if baseline.version != profile.version:
                db.add(OfferProfileVersion(
                    organization_id=organization_id,
                    offer_key=baseline.key,
                    version=baseline.version,
                    profile_snapshot=baseline.to_dict(),
                    is_active=False,
                ))
                db.flush()

        current = db.scalars(select(OfferProfileVersion).where(
            OfferProfileVersion.organization_id == organization_id,
            OfferProfileVersion.offer_key == proposal.offer_key,
            OfferProfileVersion.is_active.is_(True),
        ).with_for_update()).first()
        now = datetime.now(timezone.utc)
        if current is not None:
            current.is_active = False
            current.deactivated_at = now

        row = OfferProfileVersion(
            organization_id=organization_id,
            offer_key=proposal.offer_key,
            version=profile.version,
            profile_snapshot=profile.to_dict(),
            source_proposal_id=proposal.id,
            is_active=True,
            activated_by_id=getattr(actor, "id", None),
            activated_at=now,
        )
        db.add(row)
        db.flush()
        db.add(OfferProfileActivation(
            organization_id=organization_id,
            offer_key=proposal.offer_key,
            action="PUBLISH",
            version_id=row.id,
            previous_version_id=current.id if current else None,
            actor_id=getattr(actor, "id", None),
        ))
        proposal.status = "PUBLISHED"
        proposal.published_by_id = getattr(actor, "id", None)
        proposal.published_at = now
        db.flush()
        return row

    def rollback_profile(self, db: Any, organization_id: UUID, offer_key: str, target_version: str, actor: Any) -> Any:
        """Reativa snapshot histórico sem reescrever seu conteúdo."""
        from sqlalchemy import select
        from database.learning_models import OfferProfileActivation, OfferProfileVersion

        rows = db.scalars(select(OfferProfileVersion).where(
            OfferProfileVersion.organization_id == organization_id,
            OfferProfileVersion.offer_key == offer_key,
        ).with_for_update()).all()
        target = next((row for row in rows if row.version == target_version), None)
        if target is None:
            raise ValueError("Versão de rollback não encontrada")
        current = next((row for row in rows if row.is_active), None)
        if current is not None and current.id == target.id:
            return target
        now = datetime.now(timezone.utc)
        if current is not None:
            current.is_active = False
            current.deactivated_at = now
        target.is_active = True
        target.activated_by_id = getattr(actor, "id", None)
        target.activated_at = now
        target.deactivated_at = None
        db.add(OfferProfileActivation(
            organization_id=organization_id,
            offer_key=offer_key,
            action="ROLLBACK",
            version_id=target.id,
            previous_version_id=current.id if current else None,
            actor_id=getattr(actor, "id", None),
        ))
        db.flush()
        return target

    def list_versions(self, db: Any, organization_id: UUID, offer_key: str | None = None) -> list[Any]:
        from sqlalchemy import select
        from database.learning_models import OfferProfileVersion
        query = select(OfferProfileVersion).where(OfferProfileVersion.organization_id == organization_id)
        if offer_key:
            query = query.where(OfferProfileVersion.offer_key == offer_key)
        return db.scalars(query.order_by(OfferProfileVersion.created_at.desc())).all()

    def list_for_organization(self, db: Any, organization_id: UUID, offer_key: str | None = None) -> list[ControlledLearningProposal]:
        from sqlalchemy import select
        from src.db.models import ControlledLearningProposal
        query = select(ControlledLearningProposal).where(ControlledLearningProposal.organization_id == organization_id)
        if offer_key:
            query = query.where(ControlledLearningProposal.offer_key == offer_key)
        return db.scalars(query.order_by(ControlledLearningProposal.created_at.desc())).all()
