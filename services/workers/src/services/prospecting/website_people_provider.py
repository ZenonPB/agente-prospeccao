"""Provider passivo de pessoas publicadas no site oficial da empresa.

O provider consulta apenas o domínio recebido e um conjunto pequeno de
caminhos públicos conhecidos. Extrai exclusivamente objetos JSON-LD ``Person``
e nunca transforma cargo configurado em pessoa encontrada.
"""

from dataclasses import dataclass
import ipaddress
import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence
from urllib.parse import urljoin, urlparse

import httpx


logger = logging.getLogger(__name__)
WEBSITE_PEOPLE_PATHS = ("/", "/equipe", "/sobre", "/about", "/time")


@dataclass
class WebsiteProviderError(RuntimeError):
    """Falha observável do provider de site."""

    status: str
    message: str
    retryable: bool = False

    def __str__(self) -> str:
        return self.message


class WebsitePeopleProvider:
    """Extrai pessoas publicadas em JSON-LD no site oficial."""

    name = "website_people"
    cost = 0.25

    def __init__(
        self,
        *,
        request: Optional[Callable[..., Awaitable[httpx.Response]]] = None,
        can_consume: Optional[Callable[[], bool]] = None,
        consume: Optional[Callable[[], None]] = None,
        max_pages: int = 3,
    ) -> None:
        self._request = request
        self._can_consume = can_consume
        self._consume = consume
        self._max_pages = max(1, min(max_pages, len(WEBSITE_PEOPLE_PATHS)))
        self._max_html_bytes = 2_000_000

    async def search(self, domain: str, titles: Sequence[str]) -> List[Dict[str, Any]]:
        """Busca pessoas públicas no domínio sem sondagem ativa.

        ``titles`` é recebido para cumprir o contrato do registry; o fit é
        calculado pelo registry, mantendo este adapter limitado à coleta.
        """
        del titles
        normalized_domain = self._normalize_domain(domain)
        if not normalized_domain:
            raise WebsiteProviderError("invalid_request", "domínio inválido")
        if self._can_consume is not None and not self._can_consume():
            raise WebsiteProviderError("quota_exceeded", "cota do site esgotada")

        base = f"https://{normalized_domain}/"
        people: List[Dict[str, Any]] = []
        pages_read = 0
        for path in WEBSITE_PEOPLE_PATHS[: self._max_pages]:
            url = urljoin(base, path)
            try:
                response = await self._get(url)
            except httpx.RequestError as exc:
                raise WebsiteProviderError("failed", "falha de rede no site", True) from exc
            if response.status_code != 200:
                continue
            final_host = (urlparse(str(response.url)).hostname or "").lower().strip(".")
            allowed_hosts = {normalized_domain, f"www.{normalized_domain}"}
            if final_host not in allowed_hosts:
                logger.warning("Redirecionamento externo ignorado pelo provider de site: %s", response.url)
                continue
            pages_read += 1
            html = response.content[: self._max_html_bytes].decode(
                response.encoding or "utf-8", errors="replace",
            )
            people.extend(self._parse_jsonld(html, url, normalized_domain))

        if self._consume is not None and pages_read:
            self._consume()
        return self._dedup(people)

    async def _get(self, url: str) -> httpx.Response:
        """Executa GET público com request injetável para testes."""
        if self._request is not None:
            return await self._request(url=url)
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            return await client.get(url, headers={"Accept": "text/html,application/xhtml+xml"})

    @staticmethod
    def _normalize_domain(domain: str) -> Optional[str]:
        value = str(domain or "").strip()
        if not value:
            return None
        parsed = urlparse(value if "://" in value else f"https://{value}")
        host = (parsed.hostname or "").lower().strip(".")
        if not host or "." not in host or host.startswith("."):
            return None
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return host
        return host if address.is_global else None

    @classmethod
    def _parse_jsonld(cls, html: str, source_url: str, domain: str) -> List[Dict[str, Any]]:
        """Extrai somente nós JSON-LD do tipo Person do HTML público."""
        import re

        scripts = re.findall(
            r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
            html or "",
            flags=re.IGNORECASE | re.DOTALL,
        )
        people: List[Dict[str, Any]] = []
        for raw in scripts:
            try:
                payload = json.loads(raw.strip())
            except (TypeError, ValueError):
                continue
            for node in cls._nodes(payload):
                types = node.get("@type")
                types = types if isinstance(types, list) else [types]
                if not any(str(item).lower() == "person" for item in types):
                    continue
                name = str(node.get("name") or "").strip()
                if not name:
                    continue
                email = str(node.get("email") or "").strip() or None
                same_domain_email = bool(email and email.lower().endswith(f"@{domain}"))
                people.append({
                    "name": name,
                    "role": node.get("jobTitle") or node.get("role"),
                    "email": email,
                    "phone": node.get("telephone"),
                    "linkedin_url": cls._linkedin(node.get("sameAs")),
                    "source": "company_site",
                    "sources": [source_url],
                    "confidence": 85 if same_domain_email else 75,
                    "email_verified": False,
                })
        return people

    @staticmethod
    def _nodes(payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, dict):
            graph = payload.get("@graph")
            if isinstance(graph, list):
                return [item for item in graph if isinstance(item, dict)]
            return [payload]
        if isinstance(payload, list):
            nodes: List[Dict[str, Any]] = []
            for item in payload:
                nodes.extend(WebsitePeopleProvider._nodes(item))
            return nodes
        return []

    @staticmethod
    def _linkedin(value: Any) -> Optional[str]:
        values = value if isinstance(value, list) else [value]
        return next(
            (
                str(item).strip()
                for item in values
                if isinstance(item, str) and "linkedin.com/in/" in item.lower()
            ),
            None,
        )

    @staticmethod
    def _dedup(people: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for person in people:
            key = str(person.get("email") or person.get("linkedin_url") or person.get("name") or "").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(person)
        return result