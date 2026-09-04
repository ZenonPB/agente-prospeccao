"""ProspectingProfile — resolução centralizada do perfil de prospecção.

Embrião do contrato universal (docs/melhorias/17 e 31): um único ponto onde a
vertical da campanha é interpretada, a partir de CONFIGURAÇÃO (template +
prescoring_config), nunca de `if vertical == ...` espalhado no core.

O perfil deriva da composição de `enrichment_steps` do template (config
declarativa que já existe):

- inclui `technical_site`   → `web_presence`      (Landing Pages / sites —
  ausência de site próprio é público-alvo e presença digital vale pontos);
- só `cnpj_receita`/`business_social` → `business_opportunity` (ERP/sistemas —
  fit vem de porte/CNAE/idade, site é irrelevante);
- override explícito por `prescoring_config.profile` (ex.: `industrial`,
  onde SEO/SSL são praticamente irrelevantes e reputação pesa menos).

Adicionar uma vertical nova = inserir template com config; engine não muda.
"""
import logging
from typing import Any, Dict, Optional

from services.enrichment_capability_registry import (
    STEP_BUSINESS_SOCIAL,
    STEP_CNPJ_RECEITA,
    STEP_TECHNICAL_SITE,
)

logger = logging.getLogger(__name__)

# Fonte única dos nomes de enrichment steps (vive em capability_registry):
# renomear um step só muda lá.

PROFILE_WEB_PRESENCE = "web_presence"
PROFILE_BUSINESS = "business_opportunity"
PROFILE_INDUSTRIAL = "industrial"

# Pesos default por perfil — usados apenas quando o template não declara
# `prescoring_config.weights`. Determinísticos, sem LLM.
DEFAULT_PRESCORING_WEIGHTS: Dict[str, Dict[str, int]] = {
    PROFILE_WEB_PRESENCE: {
        "NO_OWN_WEBSITE": 25,
        "HAS_INSTAGRAM": 12,
        "HAS_PHONE": 8,
        "GOOGLE_RATING": 15,
        "GOOGLE_RATING_COUNT": 15,
    },
    PROFILE_BUSINESS: {
        "HAS_OWN_WEBSITE": 10,
        "HAS_PHONE": 10,
        "GOOGLE_RATING": 10,
        "GOOGLE_RATING_COUNT": 10,
    },
    # Site/SEO não qualifica engenharia — só presença e reputação leve.
    PROFILE_INDUSTRIAL: {
        "HAS_PHONE": 8,
        "GOOGLE_RATING": 8,
        "GOOGLE_RATING_COUNT": 8,
    },
}

# Buckets de rating_count por vertical (#09) — interpretação contextual.
# Faixas configuráveis: mesmo contagem pode ser 'bom' num segmento e 'fraco' em outro.
# raw rating_count é preservado; o pre-score usa a interpretação configurada.
RATING_COUNT_BUCKETS: Dict[str, Dict[str, tuple]] = {
    # segmento: (fraco_min, fraco_max, médio_min, médio_max, bom_min, bom_max, ótimo_min, ótimo_max)
    "psychology":    {"fraco": (0, 4),   "médio": (5, 19),  "bom": (20, 49),  "muito_bom": (50, 149), "ótimo": (150, 400)},
    "restaurant":   {"fraco": (0, 9),   "médio": (10, 49), "bom": (50, 149), "muito_bom": (150, 499), "ótimo": (500, 2000)},
    "default":      {"fraco": (0, 4),   "médio": (5, 19),  "bom": (20, 49),  "muito_bom": (50, 149),  "ótimo": (150, 400)},
}


def interpret_rating_count(profile_key: str, raw_count: Optional[int], segment: Optional[str] = None) -> Dict[str, Any]:
    """Interpreta rating_count como sinal contextual por vertical (#09).

    Args:
        profile_key: chave do perfil de prospecção.
        raw_count: valor bruto do rating_count (preservado, nunca descartado).
        segment: subnicho/segmento para buckets mais granulares (ex.: 'psychology', 'restaurant').

    Returns:
        dict com `raw`, `bucket`, `signal_score` (0-100) e `interpretation`.
    """
    raw = raw_count or 0
    if not segment:
        # Inferir segmento a partir do profile
        segment = "default"
    buckets = RATING_COUNT_BUCKETS.get(segment, RATING_COUNT_BUCKETS.get("default"))

    bucket = "fraco"
    for level, (lo, hi) in buckets.items():
        if lo <= raw <= hi:
            bucket = level
            break
    else:
        # Acima do ótimo máximo
        bucket = "ótimo" if raw > 0 else "fraco"

    # Converter bucket para score normalizado 0-100
    level_scores = {"fraco": 15, "médio": 40, "bom": 65, "muito_bom": 85, "ótimo": 100}
    score = level_scores.get(bucket, 15)

    return {
        "raw": raw,
        "bucket": bucket,
        "signal_score": score,
        "interpretation": f"rating_count={raw} classificado como '{bucket}' para segmento '{segment}'",
        "source": "rating_count_buckets",
    }


# Threshold default conservador: descarta só o claramente sem presença.
DEFAULT_PRESCORING_THRESHOLD = 40

_VALID_PROFILES = (PROFILE_WEB_PRESENCE, PROFILE_BUSINESS, PROFILE_INDUSTRIAL)


def derive_profile_key(scoring_template: Optional[Dict[str, Any]]) -> str:
    """Deriva a chave do perfil a partir do template.

    Args:
        scoring_template: dict serializado do `CampaignScoringTemplate`
            (pode ser None — template Genérico/inexistente).

    Returns:
        Uma das constantes PROFILE_* (default `web_presence` quando não há
        template, preservando o comportamento histórico de campanhas web).

    A ordem de precedência é: `prescoring_config.profile` explícito
    (fonte da verdade — a vertical declara quem é) → derivação por steps
    → default web_presence. Isso garante que o gate (`resolve_prospecting_profile`)
    e o score vetorial (`derive_profile_key`) usem o MESMO perfil.
    """
    if not scoring_template:
        return PROFILE_WEB_PRESENCE

    config: Dict[str, Any] = {}
    raw = scoring_template.get("prescoring_config")
    if isinstance(raw, dict):
        config = raw
    profile = config.get("profile")
    if profile in _VALID_PROFILES:
        return profile
    if profile:
        logger.warning(
            "prescoring_config.profile inválido (%s) — derivando dos steps", profile)

    steps = scoring_template.get("enrichment_steps") or []
    if STEP_TECHNICAL_SITE in steps:
        return PROFILE_WEB_PRESENCE
    if STEP_CNPJ_RECEITA in steps or STEP_BUSINESS_SOCIAL in steps:
        return PROFILE_BUSINESS
    return PROFILE_WEB_PRESENCE


def resolve_prospecting_profile(
    scoring_template: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Resolve o perfil de prospecção da campanha a partir do template.

    Args:
        scoring_template: dict serializado do template da campanha (ou None).

    Returns:
        Dict com `profile_key`, `profile_source` ("template_config" quando a
        vertical declarou `prescoring_config.profile`, senão "derived") e
        `prescoring` com `enabled` (default False — compatibilidade: sem
        config no template nenhum candidato é descartado), `threshold`,
        `top_k` e `weights`.
    """
    config: Dict[str, Any] = {}
    if scoring_template:
        raw = scoring_template.get("prescoring_config")
        if isinstance(raw, dict):
            config = raw

    profile_key = config.get("profile")
    if profile_key in _VALID_PROFILES:
        profile_source = "template_config"
    else:
        if profile_key:
            logger.warning(
                "prescoring_config.profile inválido (%s) — derivando dos steps",
                profile_key,
            )
        elif config.get("enabled"):
            # Gate ligado sem perfil explícito: funciona (deriva), mas é
            # frágil — a derivação depende dos steps do template.
            logger.warning(
                "prescoring_config.enabled=true sem `profile` — perfil "
                "derivado de enrichment_steps; declare `profile` explicitamente"
            )
        profile_key = derive_profile_key(scoring_template)
        profile_source = "derived"

    weights = config.get("weights")
    if not isinstance(weights, dict) or not weights:
        weights = dict(DEFAULT_PRESCORING_WEIGHTS.get(profile_key, {}))

    try:
        threshold = int(config.get("threshold", DEFAULT_PRESCORING_THRESHOLD))
    except (TypeError, ValueError):
        threshold = DEFAULT_PRESCORING_THRESHOLD
    threshold = max(0, min(100, threshold))

    top_k = config.get("top_k")
    if isinstance(top_k, int) and not isinstance(top_k, bool) and top_k > 0:
        top_k = top_k
    else:
        top_k = None

    # Gate v2 (Fase 2.x): fronteira semântica
    #   - `required_signals`: chaves de SignalKey que precisam ter sido
    #     observadas; ausentes → INSUFFICIENT_DATA (não temos base para
    #     decidir QUALIFY/DISQUALIFY só com discovery).
    #   - `on_insufficient_data`: "discard" (default — seguro) ou "promote"
    #     (opt-in: deixa o enriquecimento posterior decidir).
    raw_required = config.get("required_signals") or []
    if not isinstance(raw_required, (list, tuple)):
        raw_required = []
    required_signals = [str(k) for k in raw_required]

    on_insufficient = config.get("on_insufficient_data", "discard")
    if on_insufficient not in ("discard", "promote"):
        logger.warning(
            "prescoring_config.on_insufficient_data inválido (%r) — usando 'discard'",
            on_insufficient)
        on_insufficient = "discard"

    return {
        "profile_key": profile_key,
        "profile_source": profile_source,
        "prescoring": {
            "enabled": bool(config.get("enabled", False)),
            "threshold": threshold,
            "top_k": top_k,
            "weights": weights,
            "required_signals": required_signals,
            "on_insufficient_data": on_insufficient,
        },
    }

# Constantes de vertical extraídas do scoring_service (item 3 da Fase 2)
_WEB_PRESENCE_LABELS_CONFIG = frozenset({
    "desenvolvimento de sites", "seo / marketing digital",
})
_ERP_WEBAPP_LABELS_CONFIG = frozenset({
    "aplicações web / erp", "sistemas web / erp",
    "aplicações web completas", "erp personalizado",
    "sistema web sob medida",
})
