"""Composição read-only da Vertente efetiva para API/UI.

A fonte canônica é OfferProfile. Este serviço apenas traduz o profile efetivo
(factory + overlay da organização) para uma superfície comercial estável.
"""
from __future__ import annotations

import re
from typing import Any

from database.learning_models import OfferProfileVersion
from services.prospecting.effective_offer_registry import build_effective_registry
from services.prospecting.offer_profile_maturity import evaluate_offer_profile_maturity
from services.signal_registry import SIGNAL_REGISTRY


def _humanize(value: str) -> str:
    text = re.sub(r"[_-]+", " ", str(value or "")).strip().lower()
    return " ".join(word.capitalize() for word in text.split()) or "—"


def _signal_item(key: str, weights: dict[str, Any]) -> dict[str, Any]:
    meta = SIGNAL_REGISTRY.get(key, {})
    description = str(meta.get("description") or _humanize(key))
    return {
        "key": key,
        "label": _humanize(description),
        "description": description,
        "weight": weights.get(key),
    }


def _analysis_profile(archetype: str) -> str:
    return "web_presence" if archetype in {"web_presence", "digital_systems"} else "business_opportunity"


def _origin_keys(db: Any, organization_id: Any) -> set[str]:
    if db is None or organization_id is None:
        return set()
    rows = db.query(OfferProfileVersion.offer_key).filter(
        OfferProfileVersion.organization_id == organization_id,
        OfferProfileVersion.is_active.is_(True),
    ).all()
    return {str(row[0]) for row in rows}


def _serialize(profile: Any, *, origin: str) -> dict[str, Any]:
    profile_dict = profile.to_dict()
    signals = profile.signals or {}
    weights = signals.get("weights") if isinstance(signals.get("weights"), dict) else {}
    positive_keys = [
        *list(signals.get("positive") or []),
        *list(signals.get("optional_positive") or []),
    ]
    positive_keys = list(dict.fromkeys(str(item) for item in positive_keys if item))
    negative_keys = [
        *list(signals.get("negative") or []),
        *list(signals.get("disqualifiers") or []),
    ]
    negative_keys = list(dict.fromkeys(str(item) for item in negative_keys if item))

    enrichment = profile.enrichment or {}
    discovery = profile.discovery or {}
    decision_makers = profile.decision_makers or {}
    qualification = profile.qualification or {}
    icp = profile.icp or {}
    channels = profile.channels or {}
    maturity = evaluate_offer_profile_maturity(profile).to_dict()
    providers = list(discovery.get("providers") or [])
    steps = list(enrichment.get("steps") or [])

    return {
        "key": profile.key,
        "name": str((profile.offer or {}).get("name") or _humanize(profile.key)),
        "tagline": str((profile.offer or {}).get("tagline") or ""),
        "version": profile.version,
        "origin": origin,
        "vertical": profile.vertical,
        "archetype": profile.archetype,
        "analysis_profile": _analysis_profile(profile.archetype),
        "maturity": maturity,
        "capabilities": {
            "company_discovery": bool(providers),
            "event_discovery": "event_search" in providers,
            "website_analysis": "technical_site" in steps,
            "people_discovery": bool(enrichment.get("people_discovery")),
            "intent_detection": bool((profile.intent or {}).get("event_weights")),
        },
        "simple": {
            "segments": list(icp.get("segments") or []),
            "company_sizes": list(icp.get("company_sizes") or []),
            "exclusions": list(icp.get("exclusions") or []),
            "discovery_sources": providers,
            "positive_signals": [_signal_item(key, weights) for key in positive_keys],
            "negative_signals": [_signal_item(key, weights) for key in negative_keys],
            "decision_makers": list(decision_makers.get("priority") or decision_makers.get("roles") or []),
            "channels": list(channels.get("priority") or []),
            "qualification_questions": list(qualification.get("questions") or []),
            "analysis_flow": [
                "Encontrar possíveis clientes",
                "Coletar informações relevantes",
                "Avaliar evidências e contexto",
                "Calcular aderência",
                "Priorizar oportunidade",
            ],
        },
        "advanced": profile_dict,
    }


class VertenteService:
    def __init__(self, db: Any, organization_id: Any):
        self.db = db
        self.organization_id = organization_id

    def list(self) -> list[dict[str, Any]]:
        registry = build_effective_registry(self.db, self.organization_id)
        org_keys = _origin_keys(self.db, self.organization_id)
        items = [
            _serialize(profile, origin="organization" if profile.key in org_keys else "factory")
            for profile in registry.list()
        ]
        return sorted(items, key=lambda item: (item["vertical"], item["name"].lower()))

    def get(self, key: str) -> dict[str, Any] | None:
        registry = build_effective_registry(self.db, self.organization_id)
        profile = registry.get(key)
        if profile is None:
            return None
        origin = "organization" if key in _origin_keys(self.db, self.organization_id) else "factory"
        return _serialize(profile, origin=origin)
