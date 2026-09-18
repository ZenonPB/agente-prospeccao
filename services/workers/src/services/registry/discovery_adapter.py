"""Adapter Registry-backed para o conceito público `cnae_discovery` (parte 1).

Nome público continua `cnae_discovery`: OfferProfiles, UI e campanhas não
aprendem nada novo. Status explícitos — nunca `[]` mudo.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from services.registry.search import SearchResult
from services.registry.targeting import build_search_filters

logger = logging.getLogger(__name__)

REGISTRY_SOURCE = "brazil_company_registry"


class RegistryCnaeDiscoveryAdapter:
    """`DiscoveryProvider` com `name = "cnae_discovery"` sobre o Registry local."""

    name = "cnae_discovery"

    def __init__(
        self,
        search_service_factory: Optional[Callable[[], Any]] = None,
        *,
        budget_total: int = 50,
        legacy_run: Optional[Callable] = None,
        source_snapshot: Optional[str] = None,
    ) -> None:
        self.budget_total = budget_total
        self._search_service_factory = search_service_factory
        self._legacy_run = legacy_run
        self._source_snapshot = source_snapshot

    async def run(
        self, query: str, lead_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        result = await self.run_with_status(query, lead_context)
        return list(result["items"])


    async def run_with_status(
        self, query: str, lead_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from dataclasses import replace

        ctx = dict(lead_context or {})
        if self._search_service_factory is None:
            return _outcome("disabled", [], reason="registry_not_configured")
        filters = _filters_for(query, ctx, self.budget_total)
        if filters is None:
            return _outcome("invalid", [], reason="sem CNAE válido para o Registry")
        if self._source_snapshot is not None:
            filters = replace(filters, source_snapshot=self._source_snapshot)
        try:
            service = self._search_service_factory()
            if service is None:
                return _outcome("disabled", [], reason="registry_not_configured")
            found: SearchResult = service.search(filters)
        except Exception as exc:  # noqa: BLE001 — status explícito, nunca [] mudo
            logger.warning("Registry discovery falhou: %s", exc)
            if self._legacy_run is not None:
                try:
                    items = list(await self._legacy_run(
                        _legacy_query(query, ctx), lead_context,
                    ) or [])
                except Exception:  # noqa: BLE001 — fallback também pode falhar
                    return _outcome("failed", [], reason=str(exc)[:300])
                return _outcome("fallback", items, reason=str(exc)[:300])
            message = str(exc).lower()
            unavailable = isinstance(exc, (ConnectionError, TimeoutError)) or any(
                token in message
                for token in ("connection", "conexão", "conexao", "database", "postgres", "timeout")
            )
            status = "unavailable" if unavailable else "failed"
            return _outcome(status, [], reason=str(exc)[:300])
        if not found.items:
            return _outcome("empty", [])
        return _outcome("success", [_to_item(c) for c in found.items])

    async def compare(
        self, query: str, lead_context: Optional[Dict[str, Any]] = None,
        *, target_candidates: int | None = None,
    ) -> Dict[str, Any]:
        """Shadow barato: conta itens + overlap por CNPJ. Sem enrichment."""
        ctx = dict(lead_context or {})
        if target_candidates is not None:
            ctx["target_candidates"] = target_candidates
        registry = await self.run_with_status(query, ctx)
        legacy_items: List[Dict[str, Any]] = []
        if self._legacy_run is not None:
            try:
                legacy_items = list(await self._legacy_run(
                    _legacy_query(query, ctx), lead_context,
                ) or [])
            except Exception as exc:  # noqa: BLE001 — shadow nunca quebra o principal
                logger.warning("Shadow legado falhou: %s", exc)
        registry_cnpjs = {str(i.get("cnpj") or "") for i in registry["items"] if i.get("cnpj")}
        legacy_cnpjs = {str(i.get("cnpj") or "") for i in legacy_items if i.get("cnpj")}
        return {
            "registry_status": registry["status"],
            "registry_count": len(registry["items"]),
            "legacy_count": len(legacy_items),
            "overlap": len(registry_cnpjs & legacy_cnpjs),
            "new_candidates": len(registry_cnpjs - legacy_cnpjs),
            "enrichment_calls": 0,
            "promoted_count": 0,
        }


def _filters_for(query: str, ctx: Dict[str, Any], budget: int) -> Any | None:
    tokens = [query] if (query or "").strip() else []
    icp = dict(ctx.get("icp") or {})
    explicit_cnae = ctx.get("cnae_code")
    if explicit_cnae and not tokens:
        tokens = [str(explicit_cnae)]
    if tokens:
        icp = {**icp, "cnaes": [*tokens, *(icp.get("cnaes") or [])]}
    target = ctx.get("target_candidates", budget)
    geo = dict(icp.get("geography") or {})
    states = ctx.get("states") or geo.get("states") or []
    if states and "states" not in geo:
        geo["states"] = states
    uf = ctx.get("uf") or ctx.get("state")
    if uf and not geo.get("states"):
        geo["states"] = [uf]
    if geo:
        icp = {**icp, "geography": geo}
    municipio = ctx.get("municipio_cod")
    filters = build_search_filters(icp, target_candidates=target)
    if filters is None or municipio is None:
        return filters
    from dataclasses import replace

    return replace(filters, municipio_cod=str(municipio))


def _legacy_query(query: str, ctx: Dict[str, Any]) -> str:
    """Mantém fallback legado útil quando o Registry usa query set-based vazia."""
    if (query or "").strip():
        return query
    explicit_cnae = ctx.get("cnae_code")
    if explicit_cnae:
        return str(explicit_cnae)
    cnaes = ((ctx.get("icp") or {}).get("cnaes") or [])
    return str(cnaes[0]) if cnaes else ""


def _outcome(status: str, items: List[Dict[str, Any]], reason: str | None = None) -> Dict[str, Any]:
    outcome: Dict[str, Any] = {"status": status, "items": items, "cost": 0}
    if reason:
        outcome["reason"] = reason
    return outcome


def _to_item(candidate: Any) -> Dict[str, Any]:
    cnpj = str(getattr(candidate, "cnpj", "") or "")
    return {
        "cnpj": cnpj or None,
        "company_name": getattr(candidate, "razao_social", None)
        or getattr(candidate, "nome_fantasia", None),
        "name": getattr(candidate, "nome_fantasia", None)
        or getattr(candidate, "razao_social", None),
        "cnae_code": getattr(candidate, "cnae_principal", None),
        "cnae_description": getattr(candidate, "cnae_principal_label", None),
        "city": None,
        "state": getattr(candidate, "uf", None),
        "address": _format_address(getattr(candidate, "endereco", None)),
        "municipio_cod": getattr(candidate, "municipio_cod", None),
        "situacao": getattr(candidate, "situacao", None),
        "matriz": getattr(candidate, "matriz", None),
        "porte": getattr(candidate, "porte", None),
        "cnaes_secundarios": list(getattr(candidate, "cnaes_secundarios", None) or []),
        "place_id": f"registry_{cnpj}" if cnpj else None,
        "provider": "cnae_discovery",
        "discovery_source": REGISTRY_SOURCE,
        "provider_query": None,
        "source_snapshot": getattr(candidate, "source_snapshot", None),
        "provenance": {
            "source": getattr(candidate, "source", None) or REGISTRY_SOURCE,
            "source_snapshot": getattr(candidate, "source_snapshot", None),
            "observed_at": getattr(candidate, "observed_at", None),
        },
    }


def _format_address(address: Any) -> str | None:
    """Formata o endereço cadastral sem transformar código de município em nome."""
    if not isinstance(address, dict):
        return None
    parts = [
        address.get("tipo_logradouro"), address.get("logradouro"),
        address.get("numero"), address.get("complemento"),
        address.get("bairro"), address.get("cep"),
    ]
    value = ", ".join(str(part).strip() for part in parts if part)
    return value or None
