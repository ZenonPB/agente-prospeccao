"""Correção cirúrgica de dados (S5 do roadmap-leads, sem reset do banco).

Problema: templates `campaign_scoring_templates` gerados por IA **antes** da
regra de inversão (commit 43d874c / main) para serviços digitais podem ter em
`positive_signals` sinais do tipo "presença online / site próprio" que **aumentam**
o score — exatamente o inverso do que se vende um site (o comprador é quem NÃO tem
presença madura). Isso pontua mal prospecção que busca vender serviço digital.

Este script:
  1. Seleciona `CampaignScoringTemplate` com `is_generated=True` cuja
     `positive_signals` ainda trate "presença online/site próprio" como sinal
     POSITIVO (assinatura do template corrompido pré-S1).
  2. Para cada um: desvincula as campanhas que o usam (`scoring_template_id`)
     e as realinha ao seed global "Desenvolvimento de Sites" (que já usa
     ausência = positivo / presença madura = negativo).
  3. **Exclui** o template gerado corrompido (é reproduzível por IA; agora o
     S1 garante regenere correto).
  Não mexe em leads, orgs, contatos ou resultados de score. Idempotente.

Uso (na raiz de services/workers, por causa do env_file relativo):
    python -m src.scripts.fix_generated_web_templates             # dry-run
    python -m src.scripts.fix_generated_web_templates --apply     # aplica

Quando a operação for real, reavaliar os leads de cada campanha corrigida via
`POST /api/campaigns/{id}/reanalyze` (recomputa score com o template certo).
"""
import argparse
import logging
import re
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from sqlalchemy import func as sqlfunc

from database.session import SessionLocal
from database.models import Campaign, CampaignScoringTemplate

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# Assinatura do template corrompido: presença/posse de site tratada como sinal
# POSITIVO do lead que busca comprar serviço digital (inversão do funil).
# Lookbehind: exclui descrições de AUSÊNCIA ("sem site próprio", "sem presença
# digital") — essas descrevem o comprador e NÃO são corrompido. Como o script
# roda sobre a mesma vassoura que usa a regra de inversão (S1), falso-negativo
# é aceitável (não corrompe) — falso-positivo não.
_PRES_ASSET_RE = re.compile(
    r"(?<!sem\s)presen[çc]a\s+(online|digital|madura|s[óo]lida|profissional)|"
    r"(?<!sem\s)presen[çc]a\s+digital\s+(madura|profissional|s[óo]lida|moderna)|"
    r"(?<!sem\s)site\s+pr[óo]prio|"
    r"(?<!sem\s)website\s+pr[óo]prio",
    re.IGNORECASE,
)

# Seed global correto para realinha as campanhas (service_label exato da seed).
_SEED_LABEL = "Desenvolvimento de Sites"


def _has_presence_positive(tmpl: CampaignScoringTemplate) -> bool:
    for sig in tmpl.positive_signals or []:
        if not isinstance(sig, dict):
            continue
        label = str(sig.get("label") or "")
        descr = str(sig.get("description") or "")
        if _PRES_ASSET_RE.search(f"{label} {descr}"):
            return True
    return False


def _find_seed(db):
    label_lower = _SEED_LABEL.lower()
    return (
        db.query(CampaignScoringTemplate)
        .filter(
            CampaignScoringTemplate.organization_id.is_(None),
            CampaignScoringTemplate.is_generated.is_(False),
            sqlfunc.lower(CampaignScoringTemplate.service_label) == label_lower,
        )
        .order_by(CampaignScoringTemplate.created_at.asc())
        .first()
    )


def find_corrupt_templates(db):
    """Templates gerados por IA com presença online como sinal positivo (corrompido)."""
    generated = db.query(CampaignScoringTemplate).filter(
        CampaignScoringTemplate.is_generated.is_(True)
    ).all()
    return [t for t in generated if _has_presence_positive(t)]


def run(apply: bool = False) -> int:
    db = SessionLocal()
    try:
        corrupt = find_corrupt_templates(db)
        if not corrupt:
            logger.info("Nenhum template gerado corrompido encontrado. Nada a corrigir.")
            return 0

        seed = _find_seed(db)
        if seed is None:
            logger.warning(
                "Seed global '%s' não encontrada — campanhas serão desvinculadas "
                "(pipeline resolve template via router em vez de realinhar).",
                _SEED_LABEL,
            )

        total_realigned = 0
        for tmpl in corrupt:
            affected = (
                db.query(Campaign)
                .filter(Campaign.scoring_template_id == tmpl.id)
                .all()
            )
            n_camp = len(affected)
            mode = "APLICAR" if apply else "DRY-RUN"
            logger.info(
                "[%s] template gerado corrompido: id=%s label=%r "
                "presenca_online_positiva=sim campanhas=%d, organizacao=%s",
                mode, tmpl.id, tmpl.service_label, n_camp, tmpl.organization_id,
            )
            for camp in affected:
                logger.info(
                    "  → campanha %r (id=%s): %s",
                    camp.name, camp.id,
                    "mover para seed '" + _SEED_LABEL + "'" if seed else "desvincular template",
                )
            total_realigned += n_camp

            if apply:
                for camp in affected:
                    camp.scoring_template_id = seed.id if seed else None
                db.delete(tmpl)
            # commit só no final, em lote

        if apply:
            db.commit()
            logger.info(
                "Aplicado: %d templates gerados corrompidos removidos; "
                "%d campanhas realinhadas ao seed '%s'.",
                len(corrupt), total_realigned, _SEED_LABEL if seed else "(desvinculadas)",
            )
        else:
            logger.info(
                "DRY-RUN: %d templates corrompidos, %d campanhas impactadas. "
                "Rode com --apply para aplicar.",
                len(corrupt), total_realigned,
            )
        return 0
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.error("Erro na correção: %s", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica alterações (sem a flag, roda em dry-run).",
    )
    args = parser.parse_args()
    raise SystemExit(run(apply=args.apply))