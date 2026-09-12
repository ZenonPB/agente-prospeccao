"""Adapters versionados para integrações CRM externas.

Credenciais são resolvidas fora deste módulo e vivem apenas em memória. Os
adapters usam `httpx.AsyncClient`, redirects desabilitados, timeouts finitos e
retornam envelopes canônicos; nunca gravam segredo em logs/evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

import httpx

CRM_ADAPTER_VERSION = "v1"
SUPPORTED_CRM_PROVIDERS = ("pipedrive", "hubspot", "salesforce")
ENTITY_TYPES = {"company", "person", "opportunity", "commercial_outcome", "owner", "activity"}


@dataclass(frozen=True)
class CRMEntitySnapshot:
    entity_type: str
    entity_id: str
    organization_id: str
    version: str = CRM_ADAPTER_VERSION
    fields: Mapping[str, Any] = field(default_factory=dict)
    updated_at: str | None = None

    def __post_init__(self) -> None:
        if self.entity_type not in ENTITY_TYPES:
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
    provider: str
    version: str
    async def upsert(self, snapshot: CRMEntitySnapshot, *, idempotency_key: str) -> CRMSyncResult: ...
    async def fetch_changes(self, *, organization_id: str, cursor: str | None = None) -> tuple[list[CRMEntitySnapshot], str | None]: ...
    async def healthcheck(self) -> dict[str, Any]: ...


class BaseHTTPCRMAdapter:
    provider = ""
    version = CRM_ADAPTER_VERSION

    def __init__(self, token: str, *, base_url: str, client: httpx.AsyncClient | None = None) -> None:
        token = token.strip()
        if not token:
            raise ValueError("credencial CRM ausente")
        if not base_url.lower().startswith("https://"):
            raise ValueError("CRM exige endpoint HTTPS")
        self._token = token
        self.base_url = base_url.rstrip("/")
        self._client = client

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key[:180]
        return headers

    async def _request(self, method: str, path: str, *, params: Mapping[str, Any] | None = None, json: Any = None, headers: Mapping[str, str] | None = None) -> httpx.Response:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(20.0), follow_redirects=False)
        try:
            response = await client.request(method, f"{self.base_url}{path}", params=params, json=json, headers=dict(headers or {}))
            if 300 <= response.status_code < 400:
                raise RuntimeError("CRM retornou redirecionamento inesperado")
            response.raise_for_status()
            return response
        finally:
            if owns_client:
                await client.aclose()


class PipedriveCRMAdapter(BaseHTTPCRMAdapter):
    provider = "pipedrive"
    _entity_path = {"company": "/v1/organizations", "person": "/v1/persons", "opportunity": "/v1/deals", "activity": "/v1/activities"}

    def __init__(self, token: str, *, base_url: str = "https://api.pipedrive.com", client: httpx.AsyncClient | None = None) -> None:
        super().__init__(token, base_url=base_url, client=client)

    async def upsert(self, snapshot: CRMEntitySnapshot, *, idempotency_key: str) -> CRMSyncResult:
        path = self._entity_path.get(snapshot.entity_type)
        if not path:
            return CRMSyncResult(self.provider, "upsert", snapshot.entity_id, None, "unsupported", "entidade não possui mapeamento Pipedrive")
        remote_id = str(snapshot.fields.get("_remote_id") or "").strip() or None
        payload = {k: v for k, v in snapshot.fields.items() if not k.startswith("_") and v is not None}
        target = f"{path}/{remote_id}" if remote_id else path
        response = await self._request("PUT" if remote_id else "POST", target, params={"api_token": self._token}, json=payload, headers=self._headers(idempotency_key))
        data = response.json().get("data") or {}
        resolved_id = str(data.get("id") or remote_id or "") or None
        return CRMSyncResult(self.provider, "update" if remote_id else "create", snapshot.entity_id, resolved_id, "success")

    async def fetch_changes(self, *, organization_id: str, cursor: str | None = None) -> tuple[list[CRMEntitySnapshot], str | None]:
        params: dict[str, Any] = {"api_token": self._token, "limit": 100}
        if cursor:
            params["start"] = cursor
        response = await self._request("GET", "/v1/deals", params=params, headers=self._headers())
        body = response.json()
        snapshots = [CRMEntitySnapshot("opportunity", f"remote:{item['id']}", organization_id, fields={"_remote_id": item.get("id"), **item}) for item in (body.get("data") or []) if item.get("id") is not None]
        pagination = ((body.get("additional_data") or {}).get("pagination") or {})
        next_cursor = str(pagination.get("next_start")) if pagination.get("more_items_in_collection") else None
        return snapshots, next_cursor

    async def healthcheck(self) -> dict[str, Any]:
        response = await self._request("GET", "/v1/users/me", params={"api_token": self._token}, headers=self._headers())
        return {"provider": self.provider, "status": "ok" if response.status_code == 200 else "failed"}


class HubSpotCRMAdapter(BaseHTTPCRMAdapter):
    provider = "hubspot"
    _object_type = {"company": "companies", "person": "contacts", "opportunity": "deals", "activity": "notes"}

    def __init__(self, token: str, *, base_url: str = "https://api.hubapi.com", client: httpx.AsyncClient | None = None) -> None:
        super().__init__(token, base_url=base_url, client=client)

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        return {**super()._headers(idempotency_key), "Authorization": f"Bearer {self._token}"}

    async def upsert(self, snapshot: CRMEntitySnapshot, *, idempotency_key: str) -> CRMSyncResult:
        object_type = self._object_type.get(snapshot.entity_type)
        if not object_type:
            return CRMSyncResult(self.provider, "upsert", snapshot.entity_id, None, "unsupported", "entidade não possui mapeamento HubSpot")
        remote_id = str(snapshot.fields.get("_remote_id") or "").strip() or None
        properties = {k: v for k, v in snapshot.fields.items() if not k.startswith("_") and v is not None}
        path = f"/crm/v3/objects/{object_type}/{remote_id}" if remote_id else f"/crm/v3/objects/{object_type}"
        response = await self._request("PATCH" if remote_id else "POST", path, json={"properties": properties}, headers=self._headers(idempotency_key))
        data = response.json()
        return CRMSyncResult(self.provider, "update" if remote_id else "create", snapshot.entity_id, str(data.get("id") or remote_id or "") or None, "success", remote_version=data.get("updatedAt"))

    async def fetch_changes(self, *, organization_id: str, cursor: str | None = None) -> tuple[list[CRMEntitySnapshot], str | None]:
        params: dict[str, Any] = {"limit": 100, "archived": "false"}
        if cursor:
            params["after"] = cursor
        response = await self._request("GET", "/crm/v3/objects/deals", params=params, headers=self._headers())
        body = response.json()
        snapshots = [CRMEntitySnapshot("opportunity", f"remote:{item['id']}", organization_id, fields={"_remote_id": item.get("id"), **(item.get("properties") or {})}, updated_at=item.get("updatedAt")) for item in (body.get("results") or []) if item.get("id") is not None]
        next_cursor = (((body.get("paging") or {}).get("next") or {}).get("after"))
        return snapshots, str(next_cursor) if next_cursor is not None else None

    async def healthcheck(self) -> dict[str, Any]:
        response = await self._request("GET", "/crm/v3/objects/companies", params={"limit": 1}, headers=self._headers())
        return {"provider": self.provider, "status": "ok" if response.status_code == 200 else "failed"}


class SalesforceCRMAdapter(BaseHTTPCRMAdapter):
    provider = "salesforce"
    _object_type = {"company": "Account", "person": "Contact", "opportunity": "Opportunity", "activity": "Task"}

    def __init__(self, token: str, *, base_url: str, api_version: str = "v60.0", client: httpx.AsyncClient | None = None) -> None:
        super().__init__(token, base_url=base_url, client=client)
        self.api_version = api_version

    def _headers(self, idempotency_key: str | None = None) -> dict[str, str]:
        return {**super()._headers(idempotency_key), "Authorization": f"Bearer {self._token}"}

    async def upsert(self, snapshot: CRMEntitySnapshot, *, idempotency_key: str) -> CRMSyncResult:
        object_type = self._object_type.get(snapshot.entity_type)
        if not object_type:
            return CRMSyncResult(self.provider, "upsert", snapshot.entity_id, None, "unsupported", "entidade não possui mapeamento Salesforce")
        remote_id = str(snapshot.fields.get("_remote_id") or "").strip() or None
        payload = {k: v for k, v in snapshot.fields.items() if not k.startswith("_") and v is not None}
        if snapshot.entity_type == "opportunity" and not remote_id and not {"StageName", "CloseDate"}.issubset(payload):
            return CRMSyncResult(self.provider, "create", snapshot.entity_id, None, "unsupported", "Salesforce exige etapa e data de fechamento configuradas para criar oportunidade")
        if remote_id:
            await self._request("PATCH", f"/services/data/{self.api_version}/sobjects/{object_type}/{remote_id}", json=payload, headers=self._headers(idempotency_key))
            resolved_id = remote_id
        else:
            response = await self._request("POST", f"/services/data/{self.api_version}/sobjects/{object_type}/", json=payload, headers=self._headers(idempotency_key))
            resolved_id = str(response.json().get("id") or "") or None
        return CRMSyncResult(self.provider, "update" if remote_id else "create", snapshot.entity_id, resolved_id, "success")

    async def fetch_changes(self, *, organization_id: str, cursor: str | None = None) -> tuple[list[CRMEntitySnapshot], str | None]:
        return [], cursor

    async def healthcheck(self) -> dict[str, Any]:
        response = await self._request("GET", f"/services/data/{self.api_version}/limits", headers=self._headers())
        return {"provider": self.provider, "status": "ok" if response.status_code == 200 else "failed"}


class CRMAdapterRegistry:
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


def build_crm_adapter(provider: str, token: str, *, base_url: str | None = None, client: httpx.AsyncClient | None = None) -> CRMAdapter:
    normalized = provider.strip().lower()
    if normalized == "pipedrive":
        return PipedriveCRMAdapter(token, base_url=base_url or "https://api.pipedrive.com", client=client)
    if normalized == "hubspot":
        return HubSpotCRMAdapter(token, base_url=base_url or "https://api.hubapi.com", client=client)
    if normalized == "salesforce":
        if not base_url:
            raise ValueError("Salesforce exige a URL HTTPS da instância")
        return SalesforceCRMAdapter(token, base_url=base_url, client=client)
    raise ValueError(f"provider CRM não suportado: {normalized or 'vazio'}")
