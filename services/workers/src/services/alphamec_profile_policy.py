"""Políticas transversais do catálogo comercial AlphaMec.

Enquanto não existe evidência real suficiente para calibrar People Discovery
por oferta, o catálogo usa o contrato já validado de até duas etapas e 70% de
aderência mínima ao papel desejado. Custos e papéis continuam configuráveis em
cada OfferProfile.
"""
from __future__ import annotations

from dataclasses import replace

from services.prospecting.offer_profile import OfferProfileRegistry


DEFAULT_MIN_ROLE_FIT = 70
DEFAULT_MAX_PEOPLE_STEPS = 2


def apply_catalog_policies(registry: OfferProfileRegistry) -> OfferProfileRegistry:
    """Aplica maturidade factory e invariantes compartilhadas fora do core."""
    from services.alphamec_vertente_equalization import equalize_alphamec_vertentes

    # A equalização faz parte do catálogo factory da AlphaMec. Assim qualquer
    # consumidor do base registry enxerga a mesma Vertente; overlays publicados
    # continuam sendo aplicados depois, no registry efetivo do workspace.
    equalize_alphamec_vertentes(registry)

    for profile in list(registry.list()):
        roles = (profile.decision_makers or {}).get("roles") or []
        if not roles:
            continue
        enrichment = dict(profile.enrichment or {})
        people = dict(enrichment.get("people_discovery") or {})
        if not people:
            continue
        people["min_role_fit"] = DEFAULT_MIN_ROLE_FIT
        people["max_steps"] = DEFAULT_MAX_PEOPLE_STEPS
        enrichment["people_discovery"] = people
        registry.register(replace(profile, enrichment=enrichment))
    return registry
