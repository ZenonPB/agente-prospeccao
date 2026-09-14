"""Adapter OfferProfile → critérios de scoring (`CampaignScoringTemplate`).

Contrato entre as camadas (fonte única desta conversão):

- `OfferProfile.signals` usa chaves canônicas (`SignalKey`): listas de str
  (`{"positive": ["NO_OWN_WEBSITE"], "negative": [...], "weights": {...}}`).
- `CampaignScoringTemplate` usa critérios estruturados:
  `[{"label": ..., "description": ..., "weight_hint": "high|medium|low"}]`.
- `OfferProfile.icp` é um dict declarativo (segments, company_sizes, cnaes,
  exclusions, geography); `context_signals` do template é lista de critérios.

Regras do merge (`merge_template_signals`):

1. Critérios estruturados já existentes no template são PRESERVADOS — nunca
   sobrescritos por strings do OfferProfile.
2. Só quando o template não tem critérios (vazio/ausente) é que os sinais
   canônicos são convertidos, com metadata do `Signal Registry` (descrição
   real, sem invenção) e peso do mapa `weights` do próprio perfil.
3. Chave desconhecida (fora do registry) é ignorada com warning — nunca vira
   critério vazio nem derruba o scoring.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Mapeamento peso numérico do perfil → weight_hint do template.
# Regra explícita e testada (não calibrada por vertical: o hint só pondera
# ênfase no prompt, o peso real continua no prescoring do perfil).
HIGH_WEIGHT = 20
MEDIUM_WEIGHT = 10


def weight_hint_for(weight: Any) -> str:
    """Converte peso numérico do perfil em hint do template."""
    try:
        value = float(weight)
    except (TypeError, ValueError):
        return "medium"
    if value >= HIGH_WEIGHT:
        return "high"
    if value >= MEDIUM_WEIGHT:
        return "medium"
    return "low"


def criterion_from_signal_key(key: Any, weight: Any = None) -> Optional[Dict[str, str]]:
    """Converte uma chave canônica em critério estruturado ou None se inválida."""
    from services.signal_registry import SIGNAL_REGISTRY

    if not isinstance(key, str) or not key:
        logger.warning("Sinal de oferta inválido (não-string): %r", key)
        return None
    meta = SIGNAL_REGISTRY.get(key)
    if meta is None:
        logger.warning("Sinal de oferta fora do registry, ignorado: %r", key)
        return None
    description = str(meta.get("description") or "").strip()
    label = (description[:1].upper() + description[1:]) if description else key
    return {
        "label": label,
        "description": description,
        "weight_hint": weight_hint_for(weight),
    }


def adapt_offer_signals(signals: Optional[Dict[str, Any]]) -> Dict[str, List[Dict[str, str]]]:
    """Converte `OfferProfile.signals` em listas de critérios estruturados."""
    adapted: Dict[str, List[Dict[str, str]]] = {"positive": [], "negative": []}
    if not isinstance(signals, dict):
        return adapted
    weights = signals.get("weights") or {}
    if not isinstance(weights, dict):
        weights = {}
    for group in ("positive", "negative"):
        keys = signals.get(group) or []
        if not isinstance(keys, list):
            logger.warning("Grupo de sinais '%s' em formato inesperado: %r", group, keys)
            continue
        for key in keys:
            criterion = criterion_from_signal_key(key, weights.get(key) if isinstance(key, str) else None)
            if criterion is not None:
                adapted[group].append(criterion)
    return adapted


_ICP_LABELS = {
    "segments": "Segmentos",
    "company_sizes": "Porte",
    "cnaes": "CNAEs",
    "exclusions": "Fora do público",
    "geography": "Região",
}


def _format_icp_value(value: Any) -> str:
    if isinstance(value, dict):
        parts = []
        for item_key in ("country", "states", "cities"):
            item = value.get(item_key)
            if item:
                parts.append(", ".join(item) if isinstance(item, list) else str(item))
        return "; ".join(parts) if parts else str(value)
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def adapt_icp_to_context(icp: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Converte o dict `OfferProfile.icp` em lista de critérios de contexto."""
    if not isinstance(icp, dict):
        return []
    adapted: List[Dict[str, str]] = []
    for key, value in icp.items():
        if value is None or value == [] or value == {}:
            continue
        label = _ICP_LABELS.get(key, key.replace("_", " ").capitalize())
        adapted.append({
            "label": f"{label}: {_format_icp_value(value)}",
            "description": "",
            "weight_hint": "medium",
        })
    return adapted


def merge_template_signals(
    template: Optional[Dict[str, Any]],
    offer_signals: Optional[Dict[str, Any]] = None,
    icp: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Mescla sinais do OfferProfile no template SEM destruir critérios ricos.

    Retorna cópia do template (ou dict novo) com `positive/negative/context_signals`
    sempre como listas de critérios estruturados.
    """
    merged: Dict[str, Any] = dict(template or {})
    adapted = adapt_offer_signals(offer_signals)
    if not merged.get("positive_signals"):
        merged["positive_signals"] = adapted["positive"]
    if not merged.get("negative_signals"):
        merged["negative_signals"] = adapted["negative"]
    if not merged.get("context_signals"):
        merged["context_signals"] = adapt_icp_to_context(icp)
    for group in ("positive_signals", "negative_signals", "context_signals"):
        signals = merged.get(group)
        if signals is None:
            merged[group] = []
        elif isinstance(signals, dict):
            # Formato legado/divergente (ex.: icp dictado direto): converte.
            merged[group] = adapt_icp_to_context(signals)
        elif not isinstance(signals, list):
            logger.warning("Grupo de sinais '%s' em formato inesperado: %r", group, signals)
            merged[group] = []
    return merged
