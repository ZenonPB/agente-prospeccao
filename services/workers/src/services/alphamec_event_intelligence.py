"""Regras declarativas de contexto para eventos do portfólio AlphaMec.

Este módulo fica deliberadamente fora do núcleo genérico de prospecção. O core
apenas executa ``EventContextRule``; vocabulário de MEJ, esporte e premiação é
configuração comercial da aplicação.
"""
from __future__ import annotations

from services.prospecting.event_intelligence import EventContextRule


_AWARD_TERMS = (
    "premiação", "premiacao", "prêmio", "premio", "troféu", "trofeu",
    "medalha", "pódio", "podio", "reconhecimento", "award", "ranking",
    "campeão", "campeao", "categoria", "colocação", "colocacao",
)


def event_context_rules() -> tuple[EventContextRule, ...]:
    """Retorna as regras do portfólio em ordem de prioridade comercial."""
    return (
        EventContextRule(
            context_key="mej",
            offer_key="trophies_mej",
            segment_hint="MEJ",
            priority=300,
            terms=(
                "movimento empresa júnior", "movimento empresa junior",
                "empresa júnior", "empresa junior", "empresas juniores",
                "núcleo de empresas juniores", "nucleo de empresas juniores",
                "federação de empresas juniores", "federacao de empresas juniores",
                "brasil júnior", "brasil junior", "enej", "esej", "interej",
                "sudenej", "mej",
            ),
            demand_terms=_AWARD_TERMS,
        ),
        EventContextRule(
            context_key="sports",
            offer_key="trophies_sports",
            segment_hint="campeonatos",
            priority=200,
            terms=(
                "campeonato", "corrida", "copa", "torneio", "liga",
                "olimpíada", "olimpiada", "competição", "competicao",
                "maratona", "circuito", "festival esportivo",
                "jogos universitários", "jogos universitarios",
                "federação", "federacao", "confederação", "confederacao",
            ),
            demand_terms=_AWARD_TERMS,
        ),
        EventContextRule(
            context_key="general",
            offer_key="trophies",
            segment_hint="eventos",
            priority=100,
            fallback=True,
            terms=(),
            demand_terms=_AWARD_TERMS,
        ),
    )
