"""Adapters de providers reais para o contract DiscoveryProvider (Fase D).

Plugam GooglePlacesService, CnaeDiscoveryService, PncpService como
DiscoveryProvider. Adicionar novo provider = criar adapter + registrar.
"""
from typing import Any, Dict, List, Optional

from services.prospecting.discovery_executor import DiscoveryProvider


class GooglePlacesAdapter(DiscoveryProvider):
    """Adapter que envolve GooglePlacesService no contract DiscoveryProvider."""

    def __init__(self, places_service, budget_total: int = 100):
        # Alinhado com o `type` usado no DiscoveryPlanner (consolidação §Fase D)
        self.name = "google_places"
        self.budget_total = budget_total
        self._service = places_service

    async def run(
        self, query: str, lead_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not self._service:
            return []
        try:
            results = await self._service.search_places(
                query,
                max_results=self.budget_total,
                exclude_place_ids=(lead_context or {}).get("exclude_place_ids"),
                db=(lead_context or {}).get("db"),
                organization_id=(lead_context or {}).get("organization_id"),
                filter_city=(lead_context or {}).get("filter_city"),
                filter_state=(lead_context or {}).get("filter_state"),
                location_bias=(lead_context or {}).get("location_bias"),
                included_type=(lead_context or {}).get("included_type"),
            )
            return list(results or [])
        except Exception:
            return []


class CnaeDiscoveryAdapter(DiscoveryProvider):
    """Adapter que envolve CnaeDiscoveryService no contract DiscoveryProvider."""

    def __init__(self, cnae_service, budget_total: int = 50):
        # Alinhado com o `type` usado no DiscoveryPlanner (consolidação §Fase D)
        self.name = "cnae_discovery"
        self.budget_total = budget_total
        self._service = cnae_service

    async def run(
        self, query: str, lead_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not self._service:
            return []
        try:
            results = await self._service.search_by_cnae(
                cnae_code=query,
                state=(lead_context or {}).get("state"),
                city=(lead_context or {}).get("city"),
                limit=self.budget_total,
                cnpjs_input=(lead_context or {}).get("cnpjs_input"),
                porte_category=(lead_context or {}).get("porte_category"),
            )
            return list(results or [])
        except Exception:
            return []


def build_default_provider_registry(
    api_key: Optional[str] = None,
) -> "DiscoveryProviderRegistry":  # noqa: F821
    """Constrói o registry com os providers reais disponíveis.

    Providers opcionais (Places/CNAE) só são adicionados se api_key
    estiver setado — fallback gracioso (provider ausente é pulado pelo
    executor).
    """
    from services.prospecting.discovery_executor import DiscoveryProviderRegistry

    registry = DiscoveryProviderRegistry()
    if api_key:
        try:
            from services.places_service import GooglePlacesService
            registry.register(GooglePlacesAdapter(GooglePlacesService(api_key=api_key)))
        except Exception:
            pass
        try:
            from services.cnae_discovery_service import CnaeDiscoveryService
            registry.register(CnaeDiscoveryAdapter(CnaeDiscoveryService()))
        except Exception:
            pass
    return registry
