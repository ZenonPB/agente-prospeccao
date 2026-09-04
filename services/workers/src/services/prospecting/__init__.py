"""OfferProfile centralizado — consolidação §3 (Fase B do plano).

Resolver declarativo de ofertas comerciais. Substitui mappings hardcoded
espalhados (ICP_BY_PROFILE, ROLE_BY_PROFILE, TRIGGER_BY_PROFILE,
WEIGHTS_BY_PROFILE) por uma única entidade versionada.
"""
from services.prospecting.offer_profile import (
    OfferProfile,
    OfferProfileRegistry,
    OfferProfileResolver,
)

__all__ = ["OfferProfile", "OfferProfileRegistry", "OfferProfileResolver"]
from services.prospecting.offer_matcher import LeadOpportunity, OfferMatcher

__all__ = [
    "OfferProfile", "OfferProfileRegistry", "OfferProfileResolver",
    "LeadOpportunity", "OfferMatcher",
]
