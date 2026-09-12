"""Adapter HTTP para feeds externos de sinais comerciais.

O endpoint é configuração administrativa e continua sendo tratado como entrada
não confiável: HTTPS público, sem redirects, DNS revalidado antes da conexão.
O adapter não conhece quota nem banco; o orquestrador decide se a chamada pode
ser feita e persiste telemetria separadamente.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlsplit

import httpx


@dataclass(frozen=True)
class ExternalIntentResult:
    provider: str
    status: str
    evidence: tuple[dict[str, Any], ...]
    error_code: str | None = None
    retryable: bool = False


def _is_global_ip(value: str) -> bool:
    try:
        return bool(ipaddress.ip_address(value).is_global)
    except ValueError:
        return False


def validate_external_endpoint(url: str, *, resolved_ips: Optional[list[str]] = None) -> tuple[bool, str]:
    try:
        parsed = urlsplit((url or "").strip())
    except ValueError:
        return False, "invalid_url"
    if parsed.scheme.lower() != "https":
        return False, "https_required"
    if not parsed.hostname:
        return False, "missing_hostname"
    if parsed.username is not None or parsed.password is not None:
        return False, "credentials_not_allowed"
    if parsed.fragment:
        return False, "fragment_not_allowed"
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        return False, "local_hostname"
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if not _is_global_ip(host):
            return False, "non_public_ip"
    if resolved_ips is not None:
        if not resolved_ips:
            return False, "dns_empty"
        if any(not _is_global_ip(ip) for ip in resolved_ips):
            return False, "dns_non_public_ip"
    return True, "ok"


def _resolve_host(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({str(info[4][0]) for info in infos})


class ExternalIntentFeedProvider:
    """Coleta evidências JSON de uma fonte HTTP explicitamente configurada."""

    def __init__(
        self,
        *,
        name: str,
        endpoint: str,
        token: str = "",
        max_retries: int = 1,
        timeout_seconds: float = 8.0,
    ) -> None:
        self.name = name
        self.endpoint = (endpoint or "").strip()
        self.token = token or ""
        self.max_retries = max(0, min(int(max_retries), 5))
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 30.0))

    async def _destination_is_safe(self) -> tuple[bool, str]:
        ok, reason = validate_external_endpoint(self.endpoint)
        if not ok:
            return ok, reason
        parsed = urlsplit(self.endpoint)
        try:
            ips = await asyncio.to_thread(_resolve_host, parsed.hostname or "", parsed.port or 443)
        except (OSError, socket.gaierror):
            return False, "dns_failed"
        return validate_external_endpoint(self.endpoint, resolved_ips=ips)

    @staticmethod
    def _normalize_item(item: Any, provider: str) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        title = item.get("title") or item.get("name") or item.get("headline")
        description = item.get("description") or item.get("summary") or item.get("text")
        external_id = item.get("external_id") or item.get("id")
        url = item.get("url") or item.get("evidence_url") or item.get("link")
        if not any((title, description, external_id, url, item.get("employment"))):
            return None
        try:
            confidence = max(0.0, min(1.0, float(item.get("confidence", 0.75) or 0.75)))
        except (TypeError, ValueError):
            confidence = 0.75
        try:
            reliability = max(0.0, min(1.0, float(item.get("source_reliability", 0.7) or 0.7)))
        except (TypeError, ValueError):
            reliability = 0.7
        observed_at = item.get("observed_at") or item.get("published_at") or item.get("created_at")
        if not observed_at:
            observed_at = datetime.now(timezone.utc).isoformat()
        normalized = {
            "source": provider,
            "title": str(title)[:500] if title is not None else None,
            "description": str(description)[:3000] if description is not None else None,
            "url": str(url)[:1000] if url is not None else None,
            "external_id": str(external_id)[:255] if external_id is not None else None,
            "observed_at": str(observed_at),
            "confidence": round(confidence, 4),
            "source_reliability": round(reliability, 4),
        }
        if isinstance(item.get("employment"), dict):
            normalized["employment"] = item["employment"]
        if item.get("signal"):
            normalized["signal"] = str(item["signal"])[:120]
        return normalized

    async def collect(
        self,
        payload: dict[str, Any],
        *,
        client: Optional[httpx.AsyncClient] = None,
    ) -> ExternalIntentResult:
        if not self.endpoint:
            return ExternalIntentResult(self.name, "disabled", ())
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(
                timeout=self.timeout_seconds,
                follow_redirects=False,
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
            )
        try:
            last_error = "request_failed"
            for attempt in range(self.max_retries + 1):
                safe, reason = await self._destination_is_safe()
                if not safe:
                    return ExternalIntentResult(self.name, "invalid_destination", (), reason, False)
                try:
                    response = await client.post(self.endpoint, json=payload, headers=headers)
                except httpx.TimeoutException:
                    last_error = "timeout"
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * (2 ** attempt))
                        continue
                    return ExternalIntentResult(self.name, "failed", (), last_error, True)
                except httpx.RequestError:
                    last_error = "network_error"
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * (2 ** attempt))
                        continue
                    return ExternalIntentResult(self.name, "failed", (), last_error, True)

                if response.status_code == 429:
                    return ExternalIntentResult(self.name, "quota_exceeded", (), "http_429", True)
                if 500 <= response.status_code < 600:
                    last_error = f"http_{response.status_code}"
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * (2 ** attempt))
                        continue
                    return ExternalIntentResult(self.name, "failed", (), last_error, True)
                if response.status_code < 200 or response.status_code >= 300:
                    return ExternalIntentResult(self.name, "failed", (), f"http_{response.status_code}", False)
                try:
                    body = response.json()
                except ValueError:
                    return ExternalIntentResult(self.name, "invalid_response", (), "invalid_json", False)
                items = body.get("items") if isinstance(body, dict) else body
                if not isinstance(items, list):
                    return ExternalIntentResult(self.name, "invalid_response", (), "items_not_list", False)
                normalized = tuple(
                    value
                    for value in (self._normalize_item(item, self.name) for item in items[:100])
                    if value is not None
                )
                return ExternalIntentResult(
                    self.name,
                    "success" if normalized else "empty",
                    normalized,
                )
            return ExternalIntentResult(self.name, "failed", (), last_error, True)
        finally:
            if own_client and client is not None:
                await client.aclose()
