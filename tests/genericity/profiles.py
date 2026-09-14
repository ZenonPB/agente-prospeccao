"""OfferProfiles do Genericity Test Harness.

O contrato usa três perfis de produção arquiteturalmente distintos:
- ``trophies``: evento/timing/recorrência;
- ``web_systems_erp``: dor e complexidade operacional;
- ``mechanical_project``: contexto industrial.

Usar perfis reais impede que o harness fique verde com uma fixture mais simples
do que a configuração executada em produção.
"""
from typing import Dict, List

from services.prospecting.default_profiles import get_default_registry
from services.prospecting.offer_profile import OfferProfile, OfferProfileRegistry

TROPHIES_KEY = "trophies"
WEB_ERP_KEY = "web_systems_erp"
ENGINEERING_KEY = "mechanical_project"
PRODUCTION_KEYS = (TROPHIES_KEY, WEB_ERP_KEY, ENGINEERING_KEY)
CONTRACT_KEYS = PRODUCTION_KEYS


def production_profile(key: str) -> OfferProfile:
    profile = get_default_registry().get(key)
    if profile is None:
        raise AssertionError(
            f"OfferProfile de produção {key!r} ausente do registry padrão — "
            "o Genericity Harness depende dele."
        )
    return profile


def contract_profiles() -> Dict[str, OfferProfile]:
    return {key: production_profile(key) for key in CONTRACT_KEYS}


def contract_registry() -> OfferProfileRegistry:
    registry = OfferProfileRegistry()
    for profile in contract_profiles().values():
        registry.register(profile)
    return registry


def contract_keys() -> List[str]:
    return list(CONTRACT_KEYS)
