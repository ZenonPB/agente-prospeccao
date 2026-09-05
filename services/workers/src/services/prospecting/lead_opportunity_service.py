"""LeadOpportunityService (consolidacao item 3).

Persiste o resultado do OfferMatcher (1 lead -> N oportunidades) em uma tabela
propria, com upsert idempotente por (lead_id, offer_key).

Convivem temporariamente com `leads.evidence_score.phase3` (snapshot legado)
ate migracao completa para este modelo. Endpoint GET /api/leads/{id}/oportunidades
le apenas deste modelo (fonte de verdade).
"""
from typing import List
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from database.models import Lead, LeadOpportunityRow
from services.prospecting.offer_matcher import LeadOpportunity


class LeadOpportunityService:
    """Persistencia e leitura das oportunidades de um lead."""

    def persist_opportunities(
        self,
        db: Session,
        lead: Lead,
        opportunities: List[LeadOpportunity],
    ) -> List[LeadOpportunityRow]:
        """Upsert idempotente: cria novas e atualiza existentes por offer_key.

        Estrategia: query existing by (lead_id, offer_key) -> update OR insert.
        Sem flush intermediario; o caller decide quando commitar (consolidacao:
        "auditoria e best-effort: falha de DB loga e nunca bloqueia o pipeline").
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
            row.profile_key = opp.profile_key
            row.offer_version = getattr(opp, "offer_version", None)
            row.score = opp.score
            row.resolved_from = opp.resolved_from
            row.evidence = list(opp.evidence)
            row.signals_matched = list(opp.signals_matched)
            row.signals_missing = list(opp.signals_missing)
            row.updated_at = datetime.now(timezone.utc)
            results.append(row)
        return results

    def replace_opportunities(
        self,
        db: Session,
        lead: Lead,
        opportunities: List[LeadOpportunity],
    ) -> List[LeadOpportunityRow]:
        """Substitui o conjunto atual do lead pelo resultado mais recente.

        O matcher é recalculado durante rescoring. Remover chaves que deixaram
        de casar evita exibir oportunidades obsoletas, enquanto o histórico do
        lead permanece no JSONB legado e o caller controla a transação.
        """
        keys = {item.offer_key for item in opportunities}
        current = self.list_for_lead(db, lead.id)
        stale_ids = [row.id for row in current if row.offer_key not in keys]
        if stale_ids:
            db.execute(delete(LeadOpportunityRow).where(LeadOpportunityRow.id.in_(stale_ids)))
        return self.persist_opportunities(db, lead, opportunities)

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