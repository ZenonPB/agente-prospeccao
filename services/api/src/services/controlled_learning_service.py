"""Recomendações de learning comercial com aprovação humana explícita.

Este serviço só transforma uma comparação A/B já aprovada em uma proposta
auditável. Publicar a proposta continua sendo uma operação separada porque os
perfis de oferta ainda não possuem publicação dinâmica segura.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.db.models import ControlledLearningProposal


_EVIDENCE_FIELDS = frozenset({
    "verdict",
    "recommendation",
    "delta",
    "v1",
    "v2",
})


def build_learning_proposal(comparison: Any) -> dict[str, Any]:
    """Cria uma proposta de learning a partir de uma comparação aprovada.

    Args:
        comparison: Comparação persistida com aprovação humana e resultado
            estatisticamente conclusivo.

    Returns:
        Dicionário pronto para persistência com estado ``PROPOSED``. O payload
        não contém pesos ou thresholds e nunca representa publicação automática.

    Raises:
        ValueError: Se a comparação não tiver aprovação válida/conclusiva.
    """
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
    if (
        result.get("verdict") != expected_verdict
        or not isinstance(recommendation, str)
        or not recommendation.strip()
    ):
        raise ValueError("somente uma recomendação conclusiva pode gerar learning")

    evidence_snapshot = {
        key: deepcopy(result[key])
        for key in _EVIDENCE_FIELDS
        if key in result
    }
    return {
        "organization_id": getattr(comparison, "organization_id", None),
        "offer_key": offer_key,
        "source_comparison_id": str(comparison_id),
        "approved_version": approved_version,
        "approved_by_id": getattr(comparison, "approved_by_id", None),
        "status": "PROPOSED",
        "evidence_snapshot": evidence_snapshot,
        "requires_manual_publication": True,
    }


class ControlledLearningService:
    """Persiste propostas sem publicar ou alterar configuração ativa."""

    def create_from_comparison(
        self,
        db: Any,
        organization_id: UUID,
        comparison_id: UUID,
        actor: Any = None,
    ) -> ControlledLearningProposal:
        from sqlalchemy import func, select
        from src.db.models import CommercialComparison, ControlledLearningProposal
        from src.db.models import OrgAuditEvent
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
            db,
            organization_id,
            OrgAuditEvent.CONTROLLED_LEARNING_PROPOSED,
            actor=actor,
            target_type="controlled_learning_proposal",
            target_id=str(proposal.id),
            detail=(
                f"comparison={comparison.id}; offer={comparison.offer_key}; "
                f"proposal_version={proposal.proposal_version}; status=PROPOSED"
            ),
        )
        return proposal

    def list_for_organization(
        self,
        db: Any,
        organization_id: UUID,
        offer_key: str | None = None,
    ) -> list[ControlledLearningProposal]:
        from sqlalchemy import select
        from src.db.models import ControlledLearningProposal

        query = select(ControlledLearningProposal).where(
            ControlledLearningProposal.organization_id == organization_id,
        )
        if offer_key:
            query = query.where(ControlledLearningProposal.offer_key == offer_key)
        return db.scalars(query.order_by(ControlledLearningProposal.created_at.desc())).all()