"""Políticas transversais do catálogo comercial AlphaMec.

O threshold de aderência de cargo é mantido consistente entre ofertas enquanto
não existe evidência real suficiente para calibrá-lo por oferta. Custos, passos
e papéis continuam configuráveis em cada OfferProfile.
"""
from __future__ import annotations

from dataclasses import replace

from services.prospecting.offer_profile import OfferProfileRegistry


DEFAULT_MIN_ROLE_FIT = 70


def apply_catalog_policies(registry: OfferProfileRegistry) -> OfferProfileRegistry:
    """Aplica invariantes comerciais compartilhadas sem contaminar o core."""
    for profile in list(registry.list()):
        roles = (profile.decision_makers or {}).get("roles") or []
        if not roles:
            continue
        enrichment = dict(profile.enrichment or {})
        people = dict(enrichment.get("people_discovery") or {})
        if not people:
            continue
        people["min_role_fit"] = DEFAULT_MIN_ROLE_FIT
        enrichment["people_discovery"] = people
        registry.register(replace(profile, enrichment=enrichment))
    return registry
