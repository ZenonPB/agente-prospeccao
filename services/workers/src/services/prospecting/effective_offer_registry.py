"""Constrói o registry efetivo de OfferProfiles para um workspace.

O catálogo padrão continua sendo a base. Publicações controladas por organização
sobrescrevem somente a mesma `key`, preservando fallback/global defaults.
"""
from __future__ import annotations

from typing import Any

from database.learning_models import OfferProfileVersion
from services.prospecting.default_profiles import get_default_registry
from services.prospecting.offer_profile import OfferProfile, OfferProfileRegistry
from services.prospecting.offer_profile_validator import validate_profile


def build_effective_registry(db: Any, organization_id: Any) -> OfferProfileRegistry:
    registry = OfferProfileRegistry()
    for profile in get_default_registry().list():
        registry.register(profile)

    if db is None or organization_id is None:
        return registry

    rows = db.query(OfferProfileVersion).filter(
        OfferProfileVersion.organization_id == organization_id,
        OfferProfileVersion.is_active.is_(True),
    ).all()
    for row in rows:
        snapshot = dict(row.profile_snapshot or {})
        profile = OfferProfile.from_dict(snapshot)
        problems = [problem for problem in validate_profile(profile) if not str(problem).startswith("warning:")]
        if problems:
            # Publicações inválidas não entram silenciosamente no runtime.
            continue
        registry.register(profile)
    return registry


def get_effective_profile(db: Any, organization_id: Any, offer_key: str) -> OfferProfile | None:
    return build_effective_registry(db, organization_id).get(offer_key)
