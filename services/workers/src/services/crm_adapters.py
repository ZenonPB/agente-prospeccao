"""Contrato versionado para integrações CRM externas.

Nenhum provider é habilitado implicitamente. Adapters concretos devem resolver
credenciais pelo SecretService, usar I/O assíncrono e preservar idempotência do
sistema remoto. Este módulo define o limite arquitetural sem fingir que um CRM
está integrado antes de existir configuração e UAT reais.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

CRM_ADAPTER_VERSION = "v1"
SUPPORTED_CRM_PROVIDERS = ("pipedrive", "hubspot", "salesforce")


@dataclass(frozen=True)
class CRMEntitySnapshot:
    """Envelope canônico enviado/recebido por adapters CRM."""

    entity_type: str
    entity_id: str
    organization_id: str
    version: str = CRM_ADAPTER_VERSION
    fields: Mapping[str, Any] = field(default_factory=dict)
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.entity_type not in {
            "company",
            "person",
            "opportunity",
            "commercial_outcome",
            "owner",
            "activity",
        }:
            raise ValueError(f"entity_type não suportado: {self.entity_type}")
        if not self.entity_id or not self.organization_id:
            raise ValueError("entity_id e organization_id são obrigatórios")


@dataclass(frozen=True)
class CRMSyncResult:
    provider: str
    operation: str
    local_entity_id: str
    remote_entity_id: str | None
    status: str
    detail: str | None = None
    remote_version: str | None = None


@runtime_checkable
class CRMAdapter(Protocol):
    """Contrato mínimo para Pipedrive, HubSpot, Salesforce e futuros CRMs."""

    provider: str
    version: str

    async def upsert(self, snapshot: CRMEntitySnapshot, *, idempotency_key: str) -> CRMSyncResult:
        """Cria/atualiza a entidade remota de forma idempotente."""
        ...

    async def fetch_changes(self, *, organization_id: str, cursor: str | None = None) -> tuple[list[CRMEntitySnapshot], str | None]:
        """Lê alterações remotas sem aplicar mudanças locais diretamente."""
        ...

    async def healthcheck(self) -> dict[str, Any]:
        """Verifica credencial/configuração sem expor segredo."""
        ...


class CRMAdapterRegistry:
    """Registry explícito; ausência de adapter falha fechado."""

    def __init__(self) -> None:
        self._adapters: dict[str, CRMAdapter] = {}

    def register(self, adapter: CRMAdapter) -> None:
        provider = str(getattr(adapter, "provider", "")).strip().lower()
        version = str(getattr(adapter, "version", "")).strip()
        if provider not in SUPPORTED_CRM_PROVIDERS:
            raise ValueError(f"provider CRM não suportado: {provider or 'vazio'}")
        if version != CRM_ADAPTER_VERSION:
            raise ValueError(f"versão de adapter incompatível: {version or 'vazia'}")
        if not isinstance(adapter, CRMAdapter):
            raise TypeError("adapter não implementa CRMAdapter")
        self._adapters[provider] = adapter

    def get(self, provider: str) -> CRMAdapter:
        normalized = provider.strip().lower()
        adapter = self._adapters.get(normalized)
        if adapter is None:
            raise LookupError(f"adapter {normalized or 'vazio'} não configurado")
        return adapter

    def configured_providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))
