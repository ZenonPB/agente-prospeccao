"""Adapter OfferProfile → critérios e política de scoring.

Contrato entre as camadas:

- `OfferProfile.signals` usa chaves canônicas (`SignalKey`): listas de str.
- `CampaignScoringTemplate` usa critérios estruturados com label/description/peso.
- `OfferProfile.icp` é declarativo; `context_signals` é lista estruturada.
- A semântica de scoring que muda o comportamento do prompt é transportada em
  `scoring_policy`, derivada de chaves técnicas estáveis do OfferProfile — nunca
  de texto exibido ao usuário (`service_label`).

Regras do merge:

1. Critérios estruturados existentes são preservados.
2. Sinais canônicos só são adaptados quando o grupo correspondente está vazio.
3. Sinal desconhecido é ignorado com warning, sem derrubar o scoring.
4. A política semântica é explícita e validável: `mode` e
   `website_absence` não dependem de nomes em português.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

HIGH_WEIGHT = 20
MEDIUM_WEIGHT = 10

SCORING_MODE_GENERIC = "generic"
SCORING_MODE_WEB_PRESENCE = "web_presence"
SCORING_MODE_ERP = "erp"
WEBSITE_ABSENCE_NEUTRAL = "neutral"
WEBSITE_ABSENCE_OPPORTUNITY = "opportunity"

_ARCHETYPE_TO_MODE = {
    "web_presence": SCORING_MODE_WEB_PRESENCE,
    "digital_systems": SCORING_MODE_ERP,
}


def build_scoring_policy(
    offer_key: Optional[str],
    offer_archetype: Optional[str],
) -> Dict[str, str]:
    """Cria a política runtime de scoring a partir do contrato do OfferProfile.

    `archetype` é vocabulário técnico estável do domínio. O label comercial pode
    mudar livremente sem alterar comportamento. Arquétipos desconhecidos caem
    de forma conservadora em `generic` + ausência de site neutra.
    """
    archetype = str(offer_archetype or "generic").strip() or "generic"
    mode = _ARCHETYPE_TO_MODE.get(archetype, SCORING_MODE_GENERIC)
    website_absence = (
        WEBSITE_ABSENCE_OPPORTUNITY
        if mode == SCORING_MODE_WEB_PRESENCE
        else WEBSITE_ABSENCE_NEUTRAL
    )
    return {
        "source": "offer_profile",
        "offer_key": str(offer_key or ""),
        "archetype": archetype,
        "mode": mode,
        "website_absence": website_absence,
    }


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
            criterion = criterion_from_signal_key(
                key,
                weights.get(key) if isinstance(key, str) else None,
            )
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
    *,
    offer_key: Optional[str] = None,
    offer_archetype: Optional[str] = None,
) -> Dict[str, Any]:
    """Mescla OfferProfile no template sem destruir critérios ricos."""
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
            merged[group] = adapt_icp_to_context(signals)
        elif not isinstance(signals, list):
            logger.warning("Grupo de sinais '%s' em formato inesperado: %r", group, signals)
            merged[group] = []

    if offer_key or offer_archetype:
        merged["scoring_policy"] = build_scoring_policy(offer_key, offer_archetype)
    return merged
