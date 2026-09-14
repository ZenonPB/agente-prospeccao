"""Diagnóstico manual e seguro dos providers usados pela AlphaMec 1.0.

O serviço nunca devolve o valor de uma chave nem o corpo bruto de resposta do
provider. Ele apenas classifica disponibilidade/autorização para que um admin
possa validar a configuração do workspace sem precisar sair da aplicação.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
import sys
from typing import Any

import httpx

_workers_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "workers", "src")
if _workers_path not in sys.path:
    sys.path.insert(0, _workers_path)

from services.secret_service import SecretService  # noqa: E402


_PROVIDER_KEYS = {
    "google": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
    "hunter": "HUNTER_API_KEY",
}

_PROVIDER_LABELS = {
    "google": "Busca de empresas",
    "groq": "Inteligência artificial",
    "hunter": "Busca de decisores",
}


def classify_provider_status(status_code: int) -> str:
    if 200 <= status_code < 300:
        return "ok"
    if status_code in {401, 403}:
        return "invalid_key"
    if status_code == 429:
        return "quota_limited"
    if 500 <= status_code < 600:
        return "unavailable"
    return "rejected"


class ProviderDiagnosticsService:
    def __init__(self, timeout_seconds: float = 8.0):
        self.timeout_seconds = timeout_seconds

    async def diagnose(
        self,
        db: Any,
        organization_id: str,
        providers: list[str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        selected = providers or ["google", "groq", "hunter"]
        normalized: list[str] = []
        for provider in selected:
            key = str(provider).strip().lower()
            if key not in _PROVIDER_KEYS:
                raise ValueError(f"Provider não suportado: {provider}")
            if key not in normalized:
                normalized.append(key)

        own_client = client is None
        http_client = client or httpx.AsyncClient(timeout=self.timeout_seconds)
        try:
            results = [
                await self._check_provider(db, organization_id, provider, http_client)
                for provider in normalized
            ]
        finally:
            if own_client:
                await http_client.aclose()

        by_provider = {item["provider"]: item for item in results}
        essentials = [by_provider.get("google"), by_provider.get("groq")]
        ready = all(item and item["status"] == "ok" for item in essentials)
        return {
            "tested_at": datetime.now(timezone.utc).isoformat(),
            "ready_for_basic_prospecting": ready,
            "providers": results,
        }

    async def _check_provider(
        self,
        db: Any,
        organization_id: str,
        provider: str,
        client: httpx.AsyncClient,
    ) -> dict[str, Any]:
        key_name = _PROVIDER_KEYS[provider]
        key_value = await SecretService.resolve_key(db, organization_id, key_name)
        source = await self._key_source(db, organization_id, key_name)
        base = {
            "provider": provider,
            "label": _PROVIDER_LABELS[provider],
            "key_source": source,
        }
        if not key_value:
            return {**base, "status": "not_configured"}

        try:
            if provider == "google":
                response = await client.post(
                    "https://places.googleapis.com/v1/places:searchText",
                    headers={
                        "X-Goog-Api-Key": key_value,
                        "X-Goog-FieldMask": "places.id",
                    },
                    json={"textQuery": "IFSP Araraquara", "maxResultCount": 1},
                )
            elif provider == "groq":
                response = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {key_value}"},
                )
            else:
                response = await client.get(
                    "https://api.hunter.io/v2/account",
                    params={"api_key": key_value},
                )
            return {**base, "status": classify_provider_status(response.status_code)}
        except httpx.TimeoutException:
            return {**base, "status": "timeout"}
        except httpx.RequestError:
            return {**base, "status": "unreachable"}

    async def _key_source(self, db: Any, organization_id: str, key_name: str) -> str:
        try:
            from database.models import OrganizationSecret

            exists = (
                db.query(OrganizationSecret.id)
                .filter(
                    OrganizationSecret.organization_id == organization_id,
                    OrganizationSecret.key_name == key_name,
                )
                .first()
            )
            return "workspace" if exists else "shared"
        except Exception:  # fail-safe: source metadata is non-critical
            return "shared"
