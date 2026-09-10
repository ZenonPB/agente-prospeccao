"""Adapter assíncrono para o Hunter Domain Search.

O adapter só executa quando recebe uma chave explicitamente. A decisão de
opt-in por organização e a quota ficam no orquestrador, não neste módulo.
"""

from dataclasses import dataclass
import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence

import httpx

from services.contact_enrichment_service import parse_hunter_domain_emails


logger = logging.getLogger(__name__)
HUNTER_DOMAIN_SEARCH_URL = "https://api.hunter.io/v2/domain-search"


@dataclass
class HunterProviderError(RuntimeError):
    """Falha observável do provider Hunter."""

    status: str
    message: str
    retryable: bool = False

    def __str__(self) -> str:
        return self.message


class HunterPeopleProvider:
    """Implementa PeopleProvider usando o Domain Search do Hunter."""

    name = "hunter"
    cost = 1

    def __init__(
        self,
        api_key: str,
        *,
        request: Optional[Callable[..., Awaitable[httpx.Response]]] = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        can_consume: Optional[Callable[[], bool]] = None,
        consume: Optional[Callable[[], None]] = None,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._request = request
        self._max_retries = max(0, max_retries)
        self._retry_delay = max(0.0, retry_delay)
        self._can_consume = can_consume
        self._consume = consume

    async def search(self, domain: str, titles: Sequence[str]) -> List[Dict[str, Any]]:
        """Busca e-mails pessoais e normaliza candidatos de pessoas.

        Args:
            domain: Domínio normalizado da empresa.
            titles: Cargos desejados pelo OfferProfile.

        Returns:
            Pessoas normalizadas; lista vazia significa resposta válida sem
            resultado, não falha de provider.

        Raises:
            HunterProviderError: quando a chamada está desabilitada, falha ou
                excede quota/rate-limit.
        """
        if not self._api_key:
            raise HunterProviderError("disabled", "Hunter sem chave configurada")
        if not domain or "." not in domain:
            raise HunterProviderError("invalid_request", "domínio inválido")
        if self._can_consume is not None and not self._can_consume():
            raise HunterProviderError("quota_exceeded", "cota do Hunter esgotada", False)

        params = {"domain": domain, "type": "personal", "limit": 25}
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._get(params)
            except httpx.RequestError as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    continue
                raise HunterProviderError("failed", "falha de rede no Hunter", True) from exc

            if response.status_code == 200:
                if self._consume is not None:
                    self._consume()
                payload = self._json(response)
                people = parse_hunter_domain_emails(payload)
                return [self._normalize(person, domain) for person in people]
            if response.status_code in (401, 403):
                status = "quota_exceeded" if response.status_code == 403 else "configuration_error"
                raise HunterProviderError(status, f"Hunter respondeu HTTP {response.status_code}", response.status_code == 403)
            retryable = response.status_code == 429 or response.status_code >= 500
            if retryable and attempt < self._max_retries:
                await asyncio.sleep(self._retry_delay * (attempt + 1))
                continue
            status = "quota_exceeded" if response.status_code == 429 else "failed"
            raise HunterProviderError(status, f"Hunter respondeu HTTP {response.status_code}", retryable)
        raise HunterProviderError("failed", "Hunter não produziu resposta")

    async def _get(self, params: Dict[str, Any]) -> httpx.Response:
        """Executa GET injetável sem expor a chave em logs."""
        if self._request is not None:
            return await self._request(
                url=HUNTER_DOMAIN_SEARCH_URL,
                params=params,
                headers={"X-API-KEY": self._api_key},
            )
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            return await client.get(
                HUNTER_DOMAIN_SEARCH_URL,
                params=params,
                headers={"X-API-KEY": self._api_key},
            )

    @staticmethod
    def _json(response: httpx.Response) -> Dict[str, Any]:
        """Lê JSON do provider sem vazar o corpo de erro em exceção."""
        try:
            payload = response.json()
        except ValueError as exc:
            raise HunterProviderError("failed", "resposta inválida do Hunter") from exc
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _normalize(person: Dict[str, Any], domain: str) -> Dict[str, Any]:
        """Adiciona provenance e domínio ao candidato normalizado."""
        result = dict(person)
        result["source"] = "hunter"
        result["domain"] = domain
        result["email_verified"] = False
        result["sources"] = [
            source.get("uri")
            for source in (person.get("raw_sources") or [])
            if isinstance(source, dict) and source.get("uri")
        ]
        result.pop("raw_sources", None)
        return result