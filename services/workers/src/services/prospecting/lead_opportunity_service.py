"""LeadOpportunityService (oportunidades + histórico append-only).

Persiste o resultado do OfferMatcher (1 lead -> N oportunidades) em uma tabela
propria, com upsert idempotente por (lead_id, offer_key).

Cada avaliação gera um snapshot append-only em
`lead_opportunity_snapshots`, preservando versão do perfil, versão da
fórmula e evidências do momento da avaliação. Vendas apontam para o snapshot.

Troca de versão de OfferProfile não reescreve o histórico nem a linha
atual sem `explicit_reanalyze=True`. Novas coletas usam a versão nova; a
reavaliação de campanha ativa é explícita.
"""
import hashlib
import json
import logging
from typing import List, Optional
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database.models import Lead, LeadOpportunityRow, LeadOpportunitySnapshot
from services.prospecting.offer_matcher import LeadOpportunity

logger = logging.getLogger(__name__)

FORMULA_VERSION = "matcher-v2"


def build_snapshot_hash(
    offer_key: str,
    offer_version: Optional[str],
    score: int,
    evidence: list,
    signals_matched: list,
    signals_missing: list,
    score_breakdown: Optional[dict] = None,
) -> str:
    """Hash canônico de uma avaliação para idempotência do histórico.

    Args:
        offer_key: chave da oferta avaliada.
        offer_version: versão do perfil no momento da avaliação.
        score: score calculado pelo matcher.
        evidence: evidências da avaliação.
        signals_matched: sinais presentes.
        signals_missing: sinais ausentes.

    Returns:
        Hex SHA-256 do payload canônico ordenado.
    """
    payload = {
        "offer_key": offer_key,
        "offer_version": offer_version,
        "formula_version": FORMULA_VERSION,
        "score": score,
        "evidence": sorted(evidence or []),
        "signals_matched": sorted(signals_matched or []),
        "signals_missing": sorted(signals_missing or []),
        "score_breakdown": score_breakdown or {},
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def should_apply_rescore(
    existing_version: Optional[str],
    new_version: Optional[str],
    explicit_reanalyze: bool = False,
) -> bool:
    """Política de re-scoring com preservação de versão.

    Args:
        existing_version: versão gravada na linha atual.
        new_version: versão da nova avaliação.
        explicit_reanalyze: True quando a campanha recebeu reavaliação explícita.

    Returns:
        True se a linha atual pode ser atualizada; False preserva a versão.
    """
    if existing_version == new_version:
        return True
    if explicit_reanalyze:
        return True
    return False


class LeadOpportunityService:
    """Persistencia, histórico e leitura das oportunidades de um lead."""

    def persist_opportunities(
        self,
        db: Session,
        lead: Lead,
        opportunities: List[LeadOpportunity],
        reason: str = "enrichment",
        explicit_reanalyze: bool = False,
    ) -> List[LeadOpportunityRow]:
        """Upsert idempotente com snapshot append-only do avaliado.

        Args:
            db: sessão SQLAlchemy (o caller controla commit).
            lead: lead dono das oportunidades.
            opportunities: resultado atual do OfferMatcher.
            reason: origem da avaliação (enrichment|reanalyze|event|conversion).
            explicit_reanalyze: autoriza atualizar linha com versão diferente.

        Returns:
            Linhas atuais do lead para as ofertas avaliadas.
        """
        if not opportunities:
            return []

        offer_keys = [o.offer_key for o in opportunities]
        existing = {
            row.offer_key: row
            for row in db.scalars(
                select(LeadOpportunityRow).where(
                    LeadOpportunityRow.lead_id == lead.id,
                    LeadOpportunityRow.offer_key.in_(offer_keys),
                )
            ).all()
        }

        results: List[LeadOpportunityRow] = []
        for opp in opportunities:
            row = existing.get(opp.offer_key)
            if row is None:
                row = LeadOpportunityRow(
                    lead_id=lead.id,
                    organization_id=lead.organization_id,
                    offer_key=opp.offer_key,
                )
                db.add(row)
                db.flush()
            else:
                new_version = getattr(opp, "offer_version", None)
                if not should_apply_rescore(row.offer_version, new_version, explicit_reanalyze):
                    logger.info(
                        "Re-scoring preservado: lead %s oferta %s mantém versão %s (nova %s sem reanalyze explícito)",
                        lead.id, opp.offer_key, row.offer_version, new_version,
                    )
                    self._snapshot_row(db, row, reason="preserved_version")
                    results.append(row)
                    continue
            row.profile_key = opp.profile_key
            row.offer_version = getattr(opp, "offer_version", None)
            row.score = opp.score
            row.resolved_from = opp.resolved_from
            row.evidence = list(opp.evidence)
            row.signals_matched = list(opp.signals_matched)
            row.signals_missing = list(opp.signals_missing)
            row.score_breakdown = dict(getattr(opp, "score_breakdown", {}) or {})
            row.updated_at = datetime.now(timezone.utc)
            db.flush()
            self._snapshot_row(db, row, reason=reason)
            results.append(row)
        return results

    def replace_opportunities(
        self,
        db: Session,
        lead: Lead,
        opportunities: List[LeadOpportunity],
        reason: str = "enrichment",
        explicit_reanalyze: bool = False,
    ) -> List[LeadOpportunityRow]:
        """Substitui o conjunto atual preservando histórico das removidas.

        Linhas obsoletas recebem um snapshot final antes da remoção; a
        transação permanece sob controle do caller.
        """
        keys = {item.offer_key for item in opportunities}
        current = self.list_for_lead(db, lead.id)
        stale = [row for row in current if row.offer_key not in keys]
        for row in stale:
            self._snapshot_row(db, row, reason="removed")
        stale_ids = [row.id for row in stale]
        if stale_ids:
            db.execute(delete(LeadOpportunityRow).where(LeadOpportunityRow.id.in_(stale_ids)))
        return self.persist_opportunities(
            db, lead, opportunities, reason=reason, explicit_reanalyze=explicit_reanalyze,
        )

    def _snapshot_row(
        self,
        db: Session,
        row: LeadOpportunityRow,
        reason: str = "enrichment",
    ) -> LeadOpportunitySnapshot:
        """Registra snapshot idempotente da linha atual (append-only)."""
        snapshot_hash = build_snapshot_hash(
            row.offer_key, row.offer_version, row.score or 0,
            list(row.evidence or []), list(row.signals_matched or []),
            list(row.signals_missing or []),
            dict(row.score_breakdown or {}),
        )
        profile_snapshot_hash = hashlib.sha256(
            json.dumps(
                {"offer_version": row.offer_version, "profile_key": row.profile_key},
                sort_keys=True, ensure_ascii=False, default=str,
            ).encode("utf-8"),
        ).hexdigest()
        existing = db.scalars(
            select(LeadOpportunitySnapshot).where(
                LeadOpportunitySnapshot.lead_id == row.lead_id,
                LeadOpportunitySnapshot.snapshot_hash == snapshot_hash,
            )
        ).first()
        if existing is not None:
            return existing
        snapshot = LeadOpportunitySnapshot(
            organization_id=row.organization_id,
            lead_id=row.lead_id,
            lead_opportunity_id=row.id,
            offer_key=row.offer_key,
            offer_version=row.offer_version,
            formula_version=FORMULA_VERSION,
            profile_snapshot_hash=profile_snapshot_hash,
            score=row.score or 0,
            signals_snapshot={
                "matched": list(row.signals_matched or []),
                "missing": list(row.signals_missing or []),
                "score_breakdown": dict(row.score_breakdown or {}),
            },
            evidence_snapshot=list(row.evidence or []),
            snapshot_hash=snapshot_hash,
            reason=reason,
            scored_at=datetime.now(timezone.utc),
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    def list_for_lead(
        self,
        db: Session,
        lead_id: UUID,
    ) -> List[LeadOpportunityRow]:
        """Retorna as oportunidades do lead ordenadas por score desc."""
        return list(
            db.scalars(
                select(LeadOpportunityRow)
                .where(LeadOpportunityRow.lead_id == lead_id)
                .order_by(LeadOpportunityRow.score.desc())
            ).all()
        )

    def list_snapshots(
        self,
        db: Session,
        lead_id: UUID,
        offer_key: Optional[str] = None,
    ) -> List[LeadOpportunitySnapshot]:
        """Retorna o histórico append-only do lead (mais recente primeiro)."""
        query = select(LeadOpportunitySnapshot).where(
            LeadOpportunitySnapshot.lead_id == lead_id,
        )
        if offer_key:
            query = query.where(LeadOpportunitySnapshot.offer_key == offer_key)
        return list(
            db.scalars(query.order_by(LeadOpportunitySnapshot.created_at.desc())).all()
        )

    def latest_snapshot_for_opportunity(
        self,
        db: Session,
        opportunity_id: UUID,
    ) -> Optional[LeadOpportunitySnapshot]:
        """Snapshot mais recente de uma oportunidade atual."""
        return db.scalars(
            select(LeadOpportunitySnapshot)
            .where(LeadOpportunitySnapshot.lead_opportunity_id == opportunity_id)
            .order_by(LeadOpportunitySnapshot.created_at.desc())
        ).first()
