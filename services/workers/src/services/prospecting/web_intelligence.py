"""Public Web Intelligence (1D): fatos públicos determinísticos sobre shortlist.

Ordem econômica: o chamador filtra no PG (CNAE + UF + firmographics),
pagina com `target_candidates` e SÓ então chama este serviço — que aplica
um shortlist adicional (`max_candidates`) e busca HTTP concorrente limitada.

- Sem LLM, sem API paga, sem browser/headless, sem JS.
- FACT-only: ausência/falha de fetch vira UNKNOWN, nunca fato negativo.
- Sem acesso a DB/transação: recebe dicts, devolve evidências; quem persiste
  é o chamador (fronteira explícita, sem pool exhaustion).
- Provenance reutiliza o contrato existente: source, source_url,
  observed_at (UTC da observação real), provider, capability, kind.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from services.domain_utils import normalize_domain
from services.prospecting.safe_web_client import SafePublicWebClient
from services.prospecting.web_facts import facts_from_fetch_result

logger = logging.getLogger(__name__)

PROVIDER_NAME = "public_web_intelligence"
CAPABILITY = "website_facts"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PublicWebIntelligenceService:
    """Enriquece candidatos com FACTs web públicos (caminho 1D)."""

    def __init__(
        self,
        *,
        client_factory: Optional[Callable[[], SafePublicWebClient]] = None,
        max_concurrency: int = 3,
        max_candidates: int = 20,
    ) -> None:
        self._client_factory = client_factory or SafePublicWebClient
        self.max_concurrency = max(1, int(max_concurrency))
        self.max_candidates = max(1, int(max_candidates))

    def shortlist(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filtro barato antes de qualquer HTTP: só quem tem site próprio."""
        with_site = [
            c for c in (candidates or [])
            if normalize_domain((c or {}).get("website")) is not None
        ]
        return with_site[: self.max_candidates]

    async def enrich_candidates(
        self, candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Busca FACTs do shortlist com concorrência limitada.

        Retorna {"results": [...], "stats": {...}}. `enrichment_calls` conta
        apenas os HTTP realmente executados; `http_avoided` conta os
        candidatos poupados pelo filtro barato + shortlist.
        """
        before = len(candidates or [])
        short = self.shortlist(candidates)
        avoided = before - len(short)
        semaphore = asyncio.Semaphore(self.max_concurrency)
        results: List[Dict[str, Any]] = []
        http_calls = 0

        async def _one(candidate: Dict[str, Any]) -> Dict[str, Any]:
            nonlocal http_calls
            domain = normalize_domain(candidate.get("website"))
            url = f"https://{domain}/"
            async with semaphore:
                client = self._client_factory()
                try:
                    fetch = await client.fetch(url)
                except Exception as exc:  # noqa: BLE001 — UNKNOWN, nunca FALSE
                    logger.warning("Web intel falhou para %s: %s", domain, exc)
                    fetch = {"status": "failed", "reason": "client_error"}
                http_calls += 1
            facts = facts_from_fetch_result(fetch, url=url)
            evidence = self._to_evidence(candidate, facts, url)
            return {"candidate": candidate, "facts": facts, "evidence": evidence}

        ordered = await asyncio.gather(*(_one(c) for c in short))
        results.extend(ordered)
        return {
            "results": results,
            "stats": {
                "candidates_before": before,
                "candidates_after_filter": len(short),
                "http_calls": http_calls,
                "http_avoided": avoided,
                "enrichment_calls": http_calls,
                "promoted_count": 0,
            },
        }

    async def enrich_one(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Enriquece um candidato e expõe fatos + provenance para o orquestrador.

        O método mantém a mesma fronteira sem estado de ``enrich_candidates``:
        nenhum dado é persistido aqui e uma falha de rede continua sendo
        representada como ``UNKNOWN`` por ``facts_from_fetch_result``.
        """
        output = await self.enrich_candidates([candidate])
        if output["results"]:
            item = output["results"][0]
            evidence = item.get("evidence") or []
            provenance = dict(evidence[0]) if evidence else {
                "source": "public_web",
                "source_url": candidate.get("website"),
                "observed_at": _now_iso(),
                "provider": PROVIDER_NAME,
                "capability": CAPABILITY,
                "kind": "FACT",
            }
            return {
                "facts": item.get("facts") or {},
                "provenance": provenance,
                "evidence": evidence,
                "stats": output["stats"],
            }
        return {
            "facts": {"site_reachable": "unknown", "kind": "FACT"},
            "provenance": {
                "source": "public_web",
                "source_url": candidate.get("website"),
                "observed_at": _now_iso(),
                "provider": PROVIDER_NAME,
                "capability": CAPABILITY,
                "kind": "FACT",
            },
            "evidence": [],
            "stats": output["stats"],
        }


    @staticmethod
    def _to_evidence(
        candidate: Dict[str, Any], facts: Dict[str, Any], url: str,
    ) -> List[Dict[str, Any]]:
        """Converte FACTs no formato de `Lead.evidence` com provenance."""
        base_provenance = {
            "source": "public_web",
            "source_url": facts.get("source_url") or url,
            "observed_at": _now_iso(),
            "provider": PROVIDER_NAME,
            "capability": CAPABILITY,
            "kind": "FACT",
        }
        evidence: List[Dict[str, Any]] = []
        title = facts.get("page_title")
        evidence.append({
            "type": "WEB_FACTS",
            "title": f"Observação pública do site ({facts.get('fetch_status')})",
            "description": (
                f"Título observado: {title!r}; "
                f"meta description: {facts.get('meta_presence')}; "
                f"canonical: {facts.get('canonical_url') or 'não observado'}."
            ),
            **base_provenance,
            "facts": {k: v for k, v in facts.items() if k != "kind"},
            "candidate_ref": {
                "cnpj": candidate.get("cnpj"),
                "place_id": candidate.get("place_id"),
            },
        })
        return evidence
