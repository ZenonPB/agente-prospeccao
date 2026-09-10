"""Provider HTTP especializado para descoberta de pessoas (federado, opt-in).

Permite plugar qualquer fonte especializada (Apollo/Clay/Snov/base interna)
via endpoint JSON próprio, sem codificar um fornecedor no núcleo — o mesmo
padrão do `HttpEventDiscoveryProvider` (P1.15). A decisão de opt-in e a quota
ficam no orquestrador (`ContactEnrichmentService.for_organization`), nunca
neste módulo.

Contrato do endpoint: `GET {endpoint}?domain=...&titles=...` devolve
`{"people": [...]}` ou uma lista direta. Cada item aceita `name` (obrigatório;
sem nome o item é descartado — nunca se inventa pessoa), `role`/`jobTitle`/
`title`, `email`, `phone`/`telephone`, `linkedin_url`/`sameAs`, `confidence`,
`identity_confidence` e `buyer_role`. Lista vazia é resposta válida sem
resultado, não falha. `email_verified` é sempre `False`: verificação real é
responsabilidade exclusiva do seam `ContactVerifier`.
"""

from dataclasses import dataclass
import asyncio
import ipaddress
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence
from urllib.parse import urlparse

import httpx

from config.settings import settings


logger = logging.getLogger(__name__)


@dataclass
class HttpPeopleProviderError(RuntimeError):
    """Falha observável do provider HTTP de pessoas."""

    status: str
    message: str
    retryable: bool = False

    def __str__(self) -> str:
        return self.message


class HttpPeopleProvider:
    """Implementa PeopleProvider sobre um endpoint JSON configurável."""

    name = "people_http"
    cost = 0.5

    def __init__(
        self,
        endpoint: Optional[str],
        *,
        token: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 1,
        retry_delay: float = 1.0,
        request: Optional[Callable[..., Awaitable[httpx.Response]]] = None,
        can_consume: Optional[Callable[[], bool]] = None,
        consume: Optional[Callable[[], None]] = None,
    ) -> None:
        self._endpoint = (endpoint or "").strip().rstrip("/")
        self._token = (token or "").strip() or None
        self._timeout = max(1.0, timeout)
        self._max_retries = max(0, max_retries)
        self._retry_delay = max(0.0, retry_delay)
        self._request = request
        self._can_consume = can_consume
        self._consume = consume

    async def search(self, domain: str, titles: Sequence[str]) -> List[Dict[str, Any]]:
        """Busca pessoas no endpoint especializado e normaliza candidatos.

        Args:
            domain: Domínio normalizado da empresa.
            titles: Cargos desejados pelo OfferProfile (enviados ao endpoint;
                o fit é calculado pelo registry).

        Returns:
            Pessoas normalizadas; lista vazia significa resposta válida sem
            resultado, não falha de provider.

        Raises:
            HttpPeopleProviderError: `disabled` sem endpoint, `invalid_request`
                com domínio inválido, `quota_exceeded` sem cota, `failed` em
                rede/HTTP/JSON inválido, `configuration_error` em auth/contrato.
        """
        if not self._endpoint:
            raise HttpPeopleProviderError("disabled", "provider HTTP sem endpoint configurado")
        if not self._endpoint_valid():
            raise HttpPeopleProviderError(
                "configuration_error",
                "endpoint do provider HTTP inválido",
            )
        normalized_domain = self._normalize_domain(domain)
        if not normalized_domain:
            raise HttpPeopleProviderError("invalid_request", "domínio inválido")
        if self._can_consume is not None and not self._can_consume():
            raise HttpPeopleProviderError("quota_exceeded", "cota do provider HTTP esgotada")

        params: Dict[str, Any] = {"domain": normalized_domain}
        wanted = [str(title).strip() for title in titles or () if str(title or "").strip()]
        if wanted:
            params["titles"] = ", ".join(wanted)
        headers: Dict[str, str] = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._get(params, headers)
            except httpx.RequestError as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    continue
                raise HttpPeopleProviderError(
                    "failed", "falha de rede no provider HTTP", True,
                ) from exc

            if response.status_code == 200:
                if self._consume is not None:
                    self._consume()
                payload = self._json(response)
                return [self._normalize(item, normalized_domain) for item in payload
                        if isinstance(item, dict) and str(item.get("name") or "").strip()]
            if response.status_code == 401:
                raise HttpPeopleProviderError(
                    "configuration_error",
                    f"provider HTTP respondeu HTTP {response.status_code}",
                )
            if response.status_code in (403, 429):
                raise HttpPeopleProviderError(
                    "quota_exceeded",
                    f"provider HTTP respondeu HTTP {response.status_code}",
                    response.status_code == 429,
                )
            retryable = response.status_code >= 500
            if retryable and attempt < self._max_retries:
                await asyncio.sleep(self._retry_delay * (attempt + 1))
                continue
            raise HttpPeopleProviderError(
                "failed",
                f"provider HTTP respondeu HTTP {response.status_code}",
                retryable,
            )
        raise HttpPeopleProviderError("failed", "provider HTTP não produziu resposta")

    async def _get(self, params: Dict[str, Any], headers: Dict[str, str]) -> httpx.Response:
        """Executa GET injetável sem expor o token em logs."""
        if self._request is not None:
            return await self._request(url=self._endpoint, params=params, headers=headers)
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            return await client.get(self._endpoint, params=params, headers=headers)

    def _endpoint_valid(self) -> bool:
        """Confere esquema e host sem fazer I/O (configuração, não rede)."""
        try:
            parsed = urlparse(self._endpoint)
        except ValueError:
            return False
        return parsed.scheme in ("http", "https") and bool(parsed.hostname)

    @staticmethod
    def _json(response: httpx.Response) -> List[Dict[str, Any]]:
        """Lê a lista de pessoas sem vazar corpo de erro em exceção."""
        try:
            payload = response.json()
        except ValueError as exc:
            raise HttpPeopleProviderError("failed", "resposta inválida do provider HTTP") from exc
        items = payload.get("people", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise HttpPeopleProviderError(
                "failed", "resposta do provider HTTP não é uma lista de pessoas",
            )
        return items

    def _normalize(self, person: Dict[str, Any], domain: str) -> Dict[str, Any]:
        """Normaliza um candidato com provenance e sem verificação inventada."""
        sources = [self._endpoint]
        source_url = str(person.get("source_url") or "").strip()
        if source_url:
            sources.append(source_url)
        result: Dict[str, Any] = {
            "name": str(person.get("name") or "").strip(),
            "role": person.get("role") or person.get("jobTitle")
            or person.get("title") or person.get("job_title"),
            "email": (str(person.get("email") or "").strip() or None),
            "phone": (str(person.get("phone") or person.get("telephone") or "").strip() or None),
            "linkedin_url": self._linkedin(person),
            "source": "people_http",
            "sources": sources,
            "domain": domain,
            "confidence": self._number(person.get("confidence"), 60.0),
            "identity_confidence": self._number(person.get("identity_confidence"), 0.0),
            "email_verified": False,
        }
        buyer_role = person.get("buyer_role") or person.get("buyer_type")
        if isinstance(buyer_role, str) and buyer_role.strip():
            result["buyer_role"] = buyer_role.strip().upper()
        return result

    @staticmethod
    def _linkedin(person: Dict[str, Any]) -> Optional[str]:
        direct = person.get("linkedin_url") or person.get("linkedin")
        if isinstance(direct, str) and "linkedin.com/in/" in direct.lower():
            return direct.strip()
        same_as = person.get("sameAs")
        values = same_as if isinstance(same_as, list) else [same_as]
        return next(
            (
                str(item).strip()
                for item in values
                if isinstance(item, str) and "linkedin.com/in/" in item.lower()
            ),
            None,
        )

    @staticmethod
    def _number(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_domain(domain: str) -> Optional[str]:
        """Normaliza o domínio e rejeita host inválido ou IP privado (SSRF)."""
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
