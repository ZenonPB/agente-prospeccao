"""LeadOpportunityService (oportunidades + histórico append-only).

Persiste o resultado do OfferMatcher em uma tabela própria. Para avaliações de
enrichment/reanalyze, o serviço recalcula com o registry efetivo do workspace,
garantindo que uma publicação/rollback de OfferProfile altere de fato novas
avaliações sem reescrever histórico antigo.
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
    profile_snapshot_hash: Optional[str] = None,
    context_hash: Optional[str] = None,
) -> str:
    payload = {
        "offer_key": offer_key,
        "offer_version": offer_version,
        "formula_version": FORMULA_VERSION,
        "score": score,
        "evidence": sorted(evidence or []),
        "signals_matched": sorted(signals_matched or []),
        "signals_missing": sorted(signals_missing or []),
        "score_breakdown": score_breakdown or {},
        "profile_snapshot_hash": profile_snapshot_hash,
        "context_hash": context_hash,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def should_apply_rescore(
    existing_version: Optional[str],
    new_version: Optional[str],
    explicit_reanalyze: bool = False,
) -> bool:
    if existing_version == new_version:
        return True
    if explicit_reanalyze:
        return True
    return False


class LeadOpportunityService:
    """Persistência, histórico e leitura das oportunidades de um lead."""

    @staticmethod
    def _effective_match(db: Session, lead: Lead) -> List[LeadOpportunity]:
        """Recalcula o lead usando a versão ativa de OfferProfile da org."""
        from services.prospecting.effective_offer_registry import build_effective_registry
        from services.prospecting.offer_matcher import OfferMatcher

        target_service = getattr(getattr(lead, "campaign", None), "target_service", None) or ""
        lead_data = {
            "company_name": lead.company_name,
            "segment": getattr(lead, "category", None),
            "cnae": getattr(lead, "cnae", None),
            "company_size": None,
            "has_cnpj": bool(getattr(lead, "cnpj", None)),
            "has_phone": bool(getattr(lead, "phone", None)),
            "has_own_website": bool(getattr(lead, "website", None)),
            "has_instagram": bool(getattr(lead, "instagram_url", None)),
            "google_rating": getattr(lead, "google_rating", None),
            "google_rating_count": getattr(lead, "google_rating_count", None),
            "hosts_events": any(token in target_service.lower() for token in ("trofé", "trofe", "evento")),
        }
        return OfferMatcher(build_effective_registry(db, lead.organization_id)).match(
            lead_data, min_score=1, top_k=5,
        )

    def persist_opportunities(
        self,
        db: Session,
        lead: Lead,
        opportunities: List[LeadOpportunity],
        reason: str = "enrichment",
        explicit_reanalyze: bool = False,
    ) -> List[LeadOpportunityRow]:
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
        if reason in {"enrichment", "reanalyze"}:
            try:
                opportunities = self._effective_match(db, lead)
            except Exception as exc:  # fail-safe: keep already computed result
                logger.warning("Registry efetivo indisponível para lead %s: %s", lead.id, exc)
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

    def _snapshot_row(self, db: Session, row: LeadOpportunityRow, reason: str = "enrichment") -> LeadOpportunitySnapshot:
        from services.prospecting.evidence_context import build_evidence_context

        lead = db.get(Lead, row.lead_id)
        evidence_context = build_evidence_context(
            evidence=getattr(lead, "evidence", None) if lead else None,
            discovery_provenance=getattr(lead, "discovery_provenance", None) if lead else None,
            evidence_score=getattr(lead, "evidence_score", None) if lead else None,
        )

        # Hash do conteúdo REAL do OfferProfile efetivo. A identidade
        # (version/profile_key) não prova que a configuração era a mesma.
        # Se o perfil exato não puder ser resolvido, mantemos UNKNOWN (None)
        # em vez de fabricar uma impressão digital forte.
        profile_snapshot_hash: Optional[str] = None
        try:
            from services.prospecting.effective_offer_registry import get_effective_profile
            profile = get_effective_profile(db, row.organization_id, row.offer_key)
            if profile is not None and (
                row.offer_version is None or str(profile.version) == str(row.offer_version)
            ):
                profile_payload = profile.to_dict()
                profile_snapshot_hash = hashlib.sha256(
                    json.dumps(
                        profile_payload,
                        sort_keys=True,
                        ensure_ascii=False,
                        default=str,
                        separators=(",", ":"),
                    ).encode("utf-8"),
                ).hexdigest()
        except Exception as exc:  # fail-safe: snapshot continua possível, hash fica UNKNOWN
            logger.warning(
                "Não foi possível resolver snapshot do OfferProfile: org=%s offer=%s version=%s: %s",
                row.organization_id, row.offer_key, row.offer_version, exc,
            )

        snapshot_hash = build_snapshot_hash(
            row.offer_key, row.offer_version, row.score or 0,
            list(row.evidence or []), list(row.signals_matched or []),
            list(row.signals_missing or []), dict(row.score_breakdown or {}),
            profile_snapshot_hash=profile_snapshot_hash,
            context_hash=evidence_context["context_hash"],
        )
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
                "evidence_context": evidence_context,
            },
            # Mantém o contrato público legado (lista) para não quebrar API/UI.
            # O contexto estruturado adicional vive no signals_snapshot.
            evidence_snapshot=list(row.evidence or []),
            snapshot_hash=snapshot_hash,
            reason=reason,
            scored_at=datetime.now(timezone.utc),
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    def list_for_lead(self, db: Session, lead_id: UUID) -> List[LeadOpportunityRow]:
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
        query = select(LeadOpportunitySnapshot).where(LeadOpportunitySnapshot.lead_id == lead_id)
        if offer_key:
            query = query.where(LeadOpportunitySnapshot.offer_key == offer_key)
        return list(db.scalars(query.order_by(LeadOpportunitySnapshot.created_at.desc())).all())

    def latest_snapshot_for_opportunity(
        self,
        db: Session,
        opportunity_id: UUID,
    ) -> Optional[LeadOpportunitySnapshot]:
        return db.scalars(
            select(LeadOpportunitySnapshot)
            .where(LeadOpportunitySnapshot.lead_opportunity_id == opportunity_id)
            .order_by(LeadOpportunitySnapshot.created_at.desc())
        ).first()
