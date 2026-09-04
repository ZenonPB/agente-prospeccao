"""Catálogo de capabilities de enriquecimento (docs/melhorias/21 e 08).

Cada capability é uma fonte de informação plugável que declara:
- `step`: chave do step legado que executa a capability (compat com
  `enrichment_steps` dos templates);
- `cost`: custo relativo (low/medium/high) — referência para o planner;
- `requires`: pré-condições do contexto do lead (`has_website`, `has_cnpj`);
- `produces`: sinais canônicos (Signal Registry) que a capability contribui.

O planner (`plan_enrichment_run`) transforma o `enrichment_steps` do template
(= ordem declarada pela OFERTA, doc 08) num plano auditável: capabilities
irrelevantes são puladas com motivo (pré-condição não atendida ou skip
declarado em `enrichment_strategy.skip`) e paradas respeitam
`enrichment_strategy.stop_after`. Falha de uma capability não corrompe as
outras — cada uma é avaliada isoladamente no plano.
"""
import logging
from typing import Any, Dict, List, Optional

from services.signal_registry import SignalKey

logger = logging.getLogger(__name__)

STEP_TECHNICAL_SITE = "technical_site"
STEP_CNPJ_RECEITA = "cnpj_receita"
STEP_BUSINESS_SOCIAL = "business_social"

ENRICHMENT_STEP_KEYS = frozenset({
    STEP_TECHNICAL_SITE,
    STEP_CNPJ_RECEITA,
    STEP_BUSINESS_SOCIAL,
})

DEFAULT_ENRICHMENT_STEPS = [STEP_TECHNICAL_SITE, STEP_CNPJ_RECEITA, STEP_BUSINESS_SOCIAL]

# Pré-condições suportadas no `requires` de cada capability. O planner só
# conhece estas chaves — contexto do lead é um dict de booleans.
KNOWN_PRECONDITIONS = frozenset({"has_website", "has_cnpj"})

CAPABILITIES: Dict[str, Dict[str, Any]] = {
    STEP_TECHNICAL_SITE: {
        "capability": "website_technical",
        "cost": "high",
        "requires": ["has_website"],
        "produces": [
            # Sinais técnicos reais (CMS/SSL/performance) ainda não mapeados
            # no SignalRegistry — só o website em si é confirmado aqui.
            # HAS_INSTAGRAM pertence ao discovery/social, NÃO ao técnico.
            SignalKey.HAS_OWN_WEBSITE,
        ],
        "description": "auditoria passiva do site (CMS, SSL, performance)",
    },
    STEP_CNPJ_RECEITA: {
        "capability": "company_registry",
        "cost": "medium",
        "requires": ["has_cnpj"],
        "produces": [
            SignalKey.CNAE,
            SignalKey.COMPANY_SIZE,
        ],
        "description": "dados cadastrais Receita Federal (porte/CNAE/idade)",
    },
    STEP_BUSINESS_SOCIAL: {
        "capability": "maps_reputation",
        "cost": "low",
        "requires": [],
        "produces": [
            SignalKey.GOOGLE_RATING,
            SignalKey.GOOGLE_RATING_COUNT,
        ],
        "description": "reputação Google Maps/social — já coletada no discovery",
    },
}


def resolve_enrichment_steps(scoring_template: Optional[Dict[str, Any]]) -> list:
    """Resolve as fontes ativadas (compat: mesma API do orquestrador).

    Template novo (com `enrichment_steps`) usa a lista declarada, na ordem
    declarada pela oferta. Template antigo (flags binários) faz fallback:
    `requires_technical_report` → technical_site; `requires_business_data` →
    cnpj_receita. `business_social` é sempre incluída (reputação já chega da
    coleta).
    """
    if scoring_template is None:
        return list(DEFAULT_ENRICHMENT_STEPS)

    declared = scoring_template.get("enrichment_steps")
    if declared:
        known = []
        for s in declared:
            if s in ENRICHMENT_STEP_KEYS:
                known.append(s)
            else:
                logger.warning(
                    "enrichment_steps %r não é capability registrada — ignorada; "
                    "registre em enrichment_capability_registry.CAPABILITIES", s)
        return list(dict.fromkeys(known))

    steps: list = []
    if scoring_template.get("requires_technical_report", True):
        steps.append(STEP_TECHNICAL_SITE)
    if scoring_template.get("requires_business_data", True):
        steps.append(STEP_CNPJ_RECEITA)
    steps.append(STEP_BUSINESS_SOCIAL)
    return list(dict.fromkeys(steps))


def plan_enrichment_run(
    scoring_template: Optional[Dict[str, Any]],
    lead_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Plano auditável de execução: ordem da oferta + pré-condições + parada.

    Args:
        scoring_template: dict serializado do template (ou None → defaults).
        lead_context: {"has_website": bool, "has_cnpj": bool} do lead atual.

    Returns:
        {"runnable": [steps na ordem a executar],
         "skipped": [{"step", "reason"}...],
         "declared": ordem declarada pela oferta (antes das condições)}
    """
    ctx = lead_context or {}
    declared = resolve_enrichment_steps(scoring_template)
    strategy = (scoring_template or {}).get("enrichment_strategy") or {}
    if not isinstance(strategy, dict):
        strategy = {}
    declared_skips = set(strategy.get("skip") or [])
    stop_after = strategy.get("stop_after")

    if stop_after and stop_after not in declared:
        logger.warning("stop_after='%s' não está em enrichment_steps declarados — "
                       "ninguém é cortado; remova ou declare o step.", stop_after)

    runnable: List[str] = []
    skipped: List[Dict[str, str]] = []

    for step in declared:
        if step in declared_skips:
            skipped.append({
                "step": step,
                "reason": "skip declarado pela oferta (enrichment_strategy.skip)",
            })
            continue

        cap = CAPABILITIES.get(step, {})
        missing = [
            cond for cond in cap.get("requires", [])
            if not ctx.get(cond)
        ]
        if missing:
            skipped.append({
                "step": step,
                "reason": "pré-condição não atendida: " + ", ".join(missing),
            })
            continue

        runnable.append(step)

    if stop_after and stop_after in runnable:
        cut = runnable.index(stop_after) + 1
        for step in runnable[cut:]:
            skipped.append({
                "step": step,
                "reason": f"stop_after='{stop_after}' (parada declarada pela oferta)",
            })
        runnable = runnable[:cut]

    return {"runnable": runnable, "skipped": skipped, "declared": declared}
