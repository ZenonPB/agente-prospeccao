"""Contextos de eventos e ajustes de compatibilidade do catálogo AlphaMec.

Este módulo fica deliberadamente fora do core ``services.prospecting``: termos
do MEJ, esporte e escolhas de oferta pertencem ao portfólio/configuração, não
ao motor genérico.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from services.prospecting.offer_profile import OfferProfileRegistry


GENERAL_AWARD_TERMS = [
    "premiação", "premiacao", "prêmio", "premio", "troféu", "trofeu",
    "medalha", "pódio", "podio", "reconhecimento", "award", "ranking",
    "campeão", "campeao", "categoria", "colocação", "colocacao",
]

SPORTS_TERMS = [
    "sport", "sports", "esporte", "esportivo", "campeonato", "corrida",
    "copa", "torneio", "liga", "olimpíada", "olimpiada", "competição",
    "competicao", "maratona", "circuito", "jogos universitários",
    "jogos universitarios", "federação", "federacao", "confederação",
    "confederacao",
]

MEJ_TERMS = [
    "movimento empresa júnior", "movimento empresa junior", "empresa júnior",
    "empresa junior", "empresas juniores", "federação de empresas juniores",
    "federacao de empresas juniores", "núcleo de empresas juniores",
    "nucleo de empresas juniores", "brasil júnior", "brasil junior",
    "enej", "esej", "interej", "sudenej", "mej",
]


def _patch(registry: OfferProfileRegistry, key: str, patch: dict[str, Any], *, version: str | None = None) -> None:
    profile = registry.get(key)
    if profile is None:
        return
    discovery = dict(profile.discovery or {})
    discovery.update(patch.get("discovery") or {})
    signals = dict(profile.signals or {})
    for section, value in (patch.get("signals") or {}).items():
        if isinstance(value, list):
            signals[section] = list(dict.fromkeys([*(signals.get(section) or []), *value]))
        elif isinstance(value, dict):
            signals[section] = {**(signals.get(section) or {}), **value}
        else:
            signals[section] = value
    enrichment = dict(profile.enrichment or {})
    enrichment.update(patch.get("enrichment") or {})
    registry.register(replace(
        profile,
        version=version or profile.version,
        discovery=discovery,
        signals=signals,
        enrichment=enrichment,
    ))


def apply_alphamec_event_contexts(registry: OfferProfileRegistry) -> OfferProfileRegistry:
    """Acopla Golden Paths de evento ao catálogo sem contaminar o core."""
    # Compatibilidade: estes quatro perfis já eram v1.1 antes do Bloco A.
    for key in ("landing_page", "mechanical_project", "technical_drawing", "machine_manual"):
        profile = registry.get(key)
        if profile is not None and profile.version != "1.1":
            registry.register(replace(profile, version="1.1"))

    # O harness histórico exige 70 e a semântica de produto não pede um limiar
    # diferente. A operação muito pequena é um desqualificador legítimo para um
    # sistema sob medida de maior complexidade.
    web = registry.get("web_systems_erp")
    if web is not None:
        people = dict((web.enrichment or {}).get("people_discovery") or {})
        people["min_role_fit"] = 70
        _patch(registry, "web_systems_erp", {
            "enrichment": {**(web.enrichment or {}), "people_discovery": people},
            "signals": {"disqualifiers": ["VERY_SMALL_LOW_COMPLEXITY"]},
        })

    _patch(registry, "trophies", {
        "discovery": {
            "event_context": {
                "context_key": "general_awards",
                "terms": GENERAL_AWARD_TERMS,
                "demand_terms": GENERAL_AWARD_TERMS,
                "segment_hint": "eventos",
                "priority": 10,
                "fallback": True,
            }
        }
    })
    _patch(registry, "trophies_sports", {
        "discovery": {
            "event_context": {
                "context_key": "sports",
                "terms": SPORTS_TERMS,
                "demand_terms": [*SPORTS_TERMS, *GENERAL_AWARD_TERMS],
                "segment_hint": "campeonatos",
                "priority": 20,
                "fallback": False,
            }
        }
    })
    _patch(registry, "trophies_mej", {
        "discovery": {
            "event_context": {
                "context_key": "mej",
                "terms": MEJ_TERMS,
                "demand_terms": [*MEJ_TERMS, *GENERAL_AWARD_TERMS],
                "segment_hint": "MEJ",
                "priority": 30,
                "fallback": False,
            }
        }
    })
    return registry
