"""Persistência idempotente e política explícita de snapshots de resolução."""
import hashlib
import json
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import DecisionResolutionSnapshot


def canonical_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza um payload para serialização determinística."""
    return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


def snapshot_hash(payload: Dict[str, Any]) -> str:
    """Calcula a impressão digital SHA-256 de um payload canônico."""
    encoded = json.dumps(
        canonical_snapshot(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def should_rescore(
    previous_hash: Optional[str],
    current_hash: str,
    force: bool = False,
) -> bool:
    """Indica se uma nova avaliação deve ser registrada.

    Re-scoring automático só ocorre quando a evidência mudou. ``force`` é o
    opt-in para uma nova avaliação mesmo com payload idêntico.
    """
    return bool(force or not previous_hash or previous_hash != current_hash)


class ResolutionSnapshotService:
    """Grava snapshots sem atualizar ou remover avaliações anteriores."""

    def persist(
        self,
        db: Session,
        organization_id: UUID,
        lead_id: UUID,
        status: str,
        payload: Dict[str, Any],
        reason: str = "enrichment",
    ) -> DecisionResolutionSnapshot:
        """Obtém ou cria um snapshot idempotente para a avaliação atual."""
        normalized = canonical_snapshot(payload)
        digest = snapshot_hash(normalized)
        existing = db.scalars(select(DecisionResolutionSnapshot).where(
            DecisionResolutionSnapshot.organization_id == organization_id,
            DecisionResolutionSnapshot.lead_id == lead_id,
            DecisionResolutionSnapshot.snapshot_hash == digest,
        )).first()
        if existing is not None:
            return existing
        snapshot = DecisionResolutionSnapshot(
            organization_id=organization_id,
            lead_id=lead_id,
            status=status,
            snapshot_hash=digest,
            payload=normalized,
            reason=reason,
        )
        db.add(snapshot)
        return snapshot