"""Reprocessa leads presos com score 0 (falha transitória de scoring).

Contexto: `process_single_lead` marcava ANALISADO (com score 0) quando a
chamada ao Groq falhava (rate-limit/5xx/rede), e os batches só reprocessam
leads NOVO — então os afetados ficavam presos para sempre em ANALISADO/0.
Isso incluía justamente os leads SEM site (o público-alvo de quem vende
sites/landing pages), que pareciam "sem score" no sistema.

Este script:
  1. Seleciona leads `ANALISADO` com `qualification_score` nulo ou 0.
  2. Para cada um, re-roda `process_single_lead` (enriquecimento + scoring)
     com o contexto da campanha (target_service/segment + template), quando
     houver.
  3. Com `--fix-site-evidence`, também re-pontua leads QUE TÊM website mas
     cuja evidência gravada afirma "sem site próprio" (alucinação da LLM).
  4. Re-aplica a lógica nova: se o scoring falhar de novo, o lead volta a
     NOVO (será reprocessado no próximo batch) em vez de ficar ANALISADO/0.
  Idempotente (dry-run por padrão).

Uso (na raiz de services/workers, por causa do env_file relativo):
    python -m src.scripts.reprocess_stuck_leads                # dry-run
    python -m src.scripts.reprocess_stuck_leads --apply        # aplica
    python -m src.scripts.reprocess_stuck_leads --apply --fix-site-evidence
    python -m src.scripts.reprocess_stuck_leads --apply --limit 10
"""
import argparse
import logging
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from database.models import Lead, LeadStatus, Campaign, CampaignScoringTemplate, AnalysisProfile  # noqa: E402
from database.session import SessionLocal  # noqa: E402
from services.technical_enrichment_service import TechnicalEnrichmentService  # noqa: E402
from services.scoring_service import AIScoringService, _NO_SITE_CLAIM  # noqa: E402
from services.enrichment_orchestrator import process_single_lead  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _evidence_claims_no_site(evidence) -> bool:
    """True se alguma evidência do lead afirma que ele não tem site."""
    if not evidence:
        return False
    for e in evidence if isinstance(evidence, list) else []:
        if not isinstance(e, dict):
            continue
        text = " ".join(str(e.get(k) or "") for k in ("title", "description"))
        if _NO_SITE_CLAIM.search(text):
            return True
    return False


def collect_stuck(limit: int = 0, fix_site_evidence: bool = False):
    db = SessionLocal()
    try:
        leads = db.query(Lead).filter(
            Lead.status == LeadStatus.ANALISADO,
            (Lead.qualification_score.is_(None)) | (Lead.qualification_score == 0),
        ).all()

        if fix_site_evidence:
            base_ids = {l.id for l in leads}
            wrong = db.query(Lead).filter(Lead.website.isnot(None), Lead.website != "").all()
            leads += [
                l for l in wrong
                if l.id not in base_ids and _evidence_claims_no_site(l.evidence)
            ]
        if limit:
            leads = leads[:limit]
        return leads
    finally:
        db.close()


def _template_dict(template: CampaignScoringTemplate) -> dict:
    return {
        "service_label": template.service_label,
        "positive_signals": template.positive_signals or [],
        "negative_signals": template.negative_signals or [],
        "context_signals": template.context_signals or [],
        "extra_instructions": template.extra_instructions,
        "requires_technical_report": bool(template.requires_technical_report),
        "requires_business_data": bool(template.requires_business_data),
    }


def reprocess_one(lead: Lead, db):
    campaign = None
async def reprocess_one(lead: Lead, db):
    campaign = None
    if lead.campaign_id:
        campaign = db.query(Campaign).filter(Campaign.id == lead.campaign_id).first()

    template = None
    if campaign and campaign.scoring_template_id:
        t = db.query(CampaignScoringTemplate).filter(
            CampaignScoringTemplate.id == campaign.scoring_template_id,
        ).first()
        if t:
            template = _template_dict(t)

    analysis_profile = (
        campaign.analysis_profile if campaign and campaign.analysis_profile
        else AnalysisProfile.WEB_PRESENCE
    )

    from services.enrichment_orchestrator import process_single_lead

    _, scoring = await process_single_lead(
        lead,
        TechnicalEnrichmentService(),
        AIScoringService(),
        db,
        analysis_profile=analysis_profile,
        campaign_target_service=campaign.target_service if campaign else "",
        campaign_target_segment=campaign.target_segment if campaign else "",
        scoring_template=template,
    )
    return scoring is not None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="aplica o reprocessamento")
    parser.add_argument("--fix-site-evidence", action="store_true",
                        help="também re-pontua leads COM site cuja evidência alega 'sem site'")
    parser.add_argument("--limit", type=int, default=0, help="limita quantos leads processar")
    args = parser.parse_args()

    leads = collect_stuck(args.limit, fix_site_evidence=args.fix_site_evidence)
    logger.info("%d lead(s) para reprocessar.", len(leads))
    if not leads:
        return

    if not args.apply:
        logger.info("Dry-run — rode com --apply para reprocessar.")
        for lead in leads:
            logger.info("  reprocessaria: %s | site=%s", lead.company_name, lead.website or "sem site")
        return

    db = SessionLocal()
    import asyncio

    async def run_all() -> None:
        ok = failed = 0
        for lead in leads:
            try:
                success = await reprocess_one(lead, db)
                db.commit()
                if success:
                    ok += 1
                    logger.info(
                        "OK   %s -> score=%s status=%s",
                        lead.company_name, lead.qualification_score, lead.status.value,
                    )
                else:
                    failed += 1
                    logger.warning(
                        "FALHOU %s -> mantido %s (reprocessa no próximo batch)",
                        lead.company_name, lead.status.value,
                    )
            except Exception as exc:  # noqa: BLE001 — um lead não deve abortar o lote
                db.rollback()
                failed += 1
                logger.error("ERRO  %s: %s", lead.company_name, exc)
        logger.info("Concluído: %d ok, %d falhas.", ok, failed)

    try:
        asyncio.run(run_all())
    finally:
        db.close()


if __name__ == "__main__":
    main()
