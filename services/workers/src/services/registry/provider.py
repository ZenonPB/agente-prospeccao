"""Registry como FederatedProvider (capability company_registry, custo zero).

Ponte fina para a 1C: permite planejar/executar descoberta no universo
empresarial pelo contrato da Fase 1A sem I/O pago e sem tocar no CRM.
Não é registrado automaticamente em nenhum pipeline produtivo.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, Sequence

from sqlalchemy.orm import Session

from services.prospecting.provider_planner import ProviderPolicy
from services.registry.search import PAGE_SIZE_DEFAULT, SearchFilters, RegistrySearchService

REGISTRY_PROVIDER_NAME = "brazil_company_registry"
REGISTRY_CAPABILITY = "company_registry"


class RegistryDiscoveryProvider:
    """Adapter federado sobre o storage local do Registry (offline, free)."""

    name = REGISTRY_PROVIDER_NAME
    capability = REGISTRY_CAPABILITY

    def __init__(self, db: Session, *, page_size: int = PAGE_SIZE_DEFAULT) -> None:
        self._db = db
        self._page_size = page_size

    @property
    def policy(self) -> ProviderPolicy:
        return ProviderPolicy(
            provider=self.name,
            capability=self.capability,
            cost_per_request=0.0,
        )

    async def collect(self, request: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        limit = request.get("limit", self._page_size)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = self._page_size
        result = RegistrySearchService(self._db).search(SearchFilters(
            cnpj=request.get("cnpj"),
            cnaes=request.get("cnaes"),
            uf=request.get("uf"),
            municipio_cod=request.get("municipio_cod"),
            situacao=request.get("situacao"),
            matriz=request.get("matriz"),
            porte=request.get("porte"),
            limit=limit,
            cursor=request.get("cursor"),
        ))
        items = []
        for candidate in result.items:
            item = asdict(candidate)
            item["source"] = self.name
            items.append(item)
        return items
