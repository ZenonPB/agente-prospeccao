"""Constrói o registry efetivo de OfferProfiles para um workspace.

O catálogo padrão continua sendo a base. Publicações controladas por organização
sobrescrevem somente a mesma `key`, preservando fallback/global defaults.

Importante: a construção sempre parte do catálogo base, nunca do registry de
runtime eventualmente ligado à tarefa atual. Isso impede que o overlay do
workspace A contamine a construção do workspace B em fluxos concorrentes.
"""
from __future__ import annotations

import logging
from typing import Any

from database.learning_models import OfferProfileVersion
from services.prospecting.default_profiles import get_base_registry
from services.prospecting.offer_profile import OfferProfile, OfferProfileRegistry
from services.prospecting.offer_profile_validator import validate_profile

logger = logging.getLogger(__name__)


def build_effective_registry(db: Any, organization_id: Any) -> OfferProfileRegistry:
    # O catálogo base já contém as políticas e a equalização factory. Copiamos
    # seus profiles para um registry novo antes de aplicar qualquer overlay.
    registry = OfferProfileRegistry()
    for profile in get_base_registry().list():
        registry.register(profile)

    if db is None or organization_id is None:
        return registry

    rows = db.query(OfferProfileVersion).filter(
        OfferProfileVersion.organization_id == organization_id,
        OfferProfileVersion.is_active.is_(True),
    ).all()
    for row in rows:
        snapshot = dict(row.profile_snapshot or {})
        try:
            profile = OfferProfile.from_dict(snapshot)
        except (TypeError, ValueError):
            logger.warning("OfferProfile ativo inválido ignorado: org=%s row=%s", organization_id, getattr(row, "id", None))
            continue

        # A coluna relacional é a âncora de integridade. Um snapshot divergente
        # não pode sobrescrever outra oferta ou fingir outra versão, mesmo que o
        # JSON isoladamente seja semanticamente válido.
        if str(profile.key) != str(row.offer_key) or str(profile.version) != str(row.version):
            logger.warning(
                "OfferProfile ativo com identidade divergente ignorado: org=%s row=%s row_key=%s snapshot_key=%s row_version=%s snapshot_version=%s",
                organization_id,
                getattr(row, "id", None),
                row.offer_key,
                profile.key,
                row.version,
                profile.version,
            )
            continue

        problems = [
            problem
            for problem in validate_profile(profile)
            if not str(problem).startswith("aviso:")
        ]
        if problems:
            # Publicações inválidas não entram silenciosamente no runtime.
            logger.warning(
                "OfferProfile ativo semanticamente inválido ignorado: org=%s key=%s problemas=%s",
                organization_id,
                row.offer_key,
                "; ".join(str(item) for item in problems),
            )
            continue
        registry.register(profile)
    return registry


def get_effective_profile(db: Any, organization_id: Any, offer_key: str) -> OfferProfile | None:
    return build_effective_registry(db, organization_id).get(offer_key)


#: Provider de discovery que caracteriza prospecção baseada em eventos.
#: Uma oferta suporta Event Discovery quando o declara nos providers da
#: estratégia de discovery do perfil efetivo (base ou publicado).
EVENT_DISCOVERY_PROVIDER = "event_search"


def offer_supports_event_discovery(db: Any, organization_id: Any, offer_key: Any) -> bool:
    """Diz se a oferta efetiva do workspace suporta prospecção por eventos.

    Sem chave, perfil inexistente ou sem `event_search` nos providers →
    False (a UI omite a ação de eventos em vez de sugerir algo sem sentido).
    """
    if not offer_key or not isinstance(offer_key, str):
        return False
    profile = get_effective_profile(db, organization_id, offer_key)
    if profile is None:
        return False
    providers = (profile.discovery or {}).get("providers") or []
    return EVENT_DISCOVERY_PROVIDER in providers
