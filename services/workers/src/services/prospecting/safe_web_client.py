"""SafePublicWebClient: HTTP público com SSRF não-negociável (parte 1).

Segue o padrão canônico do repo (`external_intent_feed_provider`):
allowlist http/https, sem credenciais, IP literal deve ser global, DNS
resolve-all com TODOS os IPs validados, redirects manuais revalidados por hop.
TOCTOU resolve→connect documentado como risco residual (httpx não pinna IP
com SNI correto de forma simples).
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)


@dataclass
class SafeWebClientError(RuntimeError):
    reason: str
    message: str = ""

    def __str__(self) -> str:
        return self.message or self.reason


def is_global_ip(value: str) -> bool:
    try:
        return bool(ipaddress.ip_address(value).is_global)
    except ValueError:
        return False


class SafePublicWebClient:
    """GET público com limites: timeout, redirects manuais, payload bounded."""

    def __init__(
        self,
        *,
        timeout_connect: float = 5.0,
        timeout_read: float = 10.0,
        timeout_total: float = 20.0,
        max_redirects: int = 5,
        max_bytes: int = 2_000_000,
        resolver: Optional[Callable[[str, int], list[str]]] = None,
        transport: Any | None = None,
        user_agent: str = "ProspectAI-WebIntelligence/1.0 (+passive-observation)",
    ) -> None:
        self.timeout_connect = timeout_connect
        self.timeout_read = timeout_read
        self.timeout_total = max(0.1, float(timeout_total))
        self.max_redirects = max(0, max_redirects)
        self.max_bytes = max_bytes
        self._resolver = resolver or _resolve_host
        self._transport = transport
        self._user_agent = user_agent

    def validate_url(self, url: str) -> str:
        """Valida sintaxe da URL sem I/O. Levanta SafeWebClientError."""
        try:
            parsed = urlsplit((url or "").strip())
        except ValueError:
            raise SafeWebClientError("invalid_url")
        if parsed.scheme.lower() not in ("http", "https"):
            raise SafeWebClientError("scheme_not_allowed")
        if not parsed.hostname:
            raise SafeWebClientError("missing_hostname")
        if parsed.username is not None or parsed.password is not None:
            raise SafeWebClientError("credentials_not_allowed")
        try:
            port = parsed.port
        except ValueError:
            raise SafeWebClientError("invalid_port")
        if port is not None and not (1 <= port <= 65535):
            raise SafeWebClientError("invalid_port")
        host = parsed.hostname.rstrip(".").lower()
        labels = host.split(".")
        if "localhost" in labels:
            raise SafeWebClientError("local_hostname")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            if not is_global_ip(host):
                raise SafeWebClientError("non_public_ip")
        return parsed.geturl()

    def validate_destination(self, host: str, resolved_ips: list[str]) -> None:
        """Valida TODOS os IPs resolvidos. Levanta SafeWebClientError."""
        if not resolved_ips:
            raise SafeWebClientError("dns_empty")
        if any(not is_global_ip(ip) for ip in resolved_ips):
            raise SafeWebClientError("dns_non_public_ip")

    async def _check_redirect(self, current_url: str, location: str, *, hop: int) -> str:
        """Valida um hop de redirect. Levanta SafeWebClientError se inseguro."""
        if hop > self.max_redirects:
            raise SafeWebClientError("too_many_redirects")
        from urllib.parse import urljoin

        target = urljoin(current_url, location)
        self.validate_url(target)
        return target

    async def _check_destination(self, url: str) -> None:
        """Resolve o host e valida TODOS os IPs (fail-closed em DNS)."""
        from urllib.parse import urlsplit as _split

        parsed = _split(url)
        host = parsed.hostname or ""
        try:
            import asyncio as _asyncio

            default_port = 443 if parsed.scheme.lower() == "https" else 80
            ips = await _asyncio.to_thread(self._resolver, host, parsed.port or default_port)
        except Exception:
            raise SafeWebClientError("dns_failed")
        self.validate_destination(host, ips)

    async def fetch(self, url: str) -> Dict[str, Any]:
        """Executa GET com teto total, além dos timeouts de conexão/leitura."""
        try:
            async with asyncio.timeout(self.timeout_total):
                return await self._fetch_impl(url)
        except TimeoutError:
            return {"status": "failed", "reason": "timeout", "retryable": True}

    async def _fetch_impl(self, url: str) -> Dict[str, Any]:
        """GET público com redirect manual revalidado e payload bounded.

        Retorna dict com `status` em {"ok", "http_error", "failed"} — nunca
        levanta em falha de rede (fail-closed observável). Levanta
        SafeWebClientError em destino inseguro, Content-Type proibido ou
        payload acima do limite.
        """
        import httpx as _httpx

        target = self.validate_url(url)
        redirects = 0
        timeout = _httpx.Timeout(self.timeout_read, connect=self.timeout_connect)
        async with _httpx.AsyncClient(
            timeout=timeout, follow_redirects=False, transport=self._transport,
            headers={"User-Agent": self._user_agent, "Accept": "text/html,application/xhtml+xml"},
        ) as client:
            while True:
                await self._check_destination(target)
                try:
                    async with client.stream("GET", target) as response:
                        if 300 <= response.status_code < 400 and response.headers.get("location"):
                            redirects += 1
                            target = await self._check_redirect(
                                target, response.headers["location"], hop=redirects,
                            )
                            continue
                        if response.status_code != 200:
                            return {
                                "status": "http_error", "status_code": response.status_code,
                                "retryable": 500 <= response.status_code < 600,
                            }
                        content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
                        if content_type not in ALLOWED_CONTENT_TYPES:
                            raise SafeWebClientError("content_type_not_allowed")
                        content_length = response.headers.get("content-length")
                        if content_length is not None:
                            try:
                                if int(content_length) > self.max_bytes:
                                    raise SafeWebClientError("payload_too_large")
                            except ValueError:
                                # Um header malformado não libera um corpo sem limite;
                                # o teto continua sendo aplicado pelo streaming.
                                pass
                        body = await self._read_bounded(response)
                        encoding = response.encoding or "utf-8"
                        return {
                            "status": "ok", "status_code": 200, "url": str(response.url),
                            "redirects": redirects, "content_type": content_type,
                            "text": body.decode(encoding, errors="replace"),
                            "bytes": len(body),
                        }
                except _httpx.TimeoutException:
                    return {"status": "failed", "reason": "timeout", "retryable": True}
                except _httpx.RequestError:
                    return {"status": "failed", "reason": "network_error", "retryable": True}

    async def _read_bounded(self, response: Any) -> bytes:
        chunks: List[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > self.max_bytes:
                raise SafeWebClientError("payload_too_large")
            chunks.append(chunk)
        return b"".join(chunks)


ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml")





def _resolve_host(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({str(info[4][0]) for info in infos})
