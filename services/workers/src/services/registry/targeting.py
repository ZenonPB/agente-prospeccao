"""Targeting OfferProfile → Registry (`icp` → `SearchFilters`).

Regras (§7/§8 do plano, ajustes obrigatórios aprovados):

- Registry exige ≥1 CNAE válido — sem CNAE, retorna None (chamador usa
  providers existentes; nunca varre o universo).
- Geografia: só 1 UF vira filtro; município por código só quando o caller já
  resolveu; raio/cidade-nome NUNCA viram município — vão para `unapplied`.
- `target_candidates` vira `limit` da query PG (primeiro filtro no banco,
  depois paginação) — nunca materializa o universo para fatiar em Python.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from services.registry.cnae_matching import CnaeFilter, parse_cnae_tokens
from services.registry.search import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX, SearchFilters


# Códigos do campo PORTE do layout EMPRESAS da Receita Federal.
# O Registry armazena o código, enquanto OfferProfile usa rótulos comerciais.
PORTE_CODES = {
    "ME": "01",
    "EPP": "03",
    "GE": "05",
}


@dataclass(frozen=True)
class TargetingOutcome:
    filters: SearchFilters | None
    unapplied: tuple[str, ...] = ()


class TargetingResult:
    """Namespace compatível com `TargetingResult.from_offer(icp, discovery)`."""

    @staticmethod
    def from_offer(
        icp: Mapping[str, Any] | None,
        discovery: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> TargetingOutcome:
        filters = build_search_filters(icp, discovery, **kwargs)
        if filters is None:
            return TargetingOutcome(None, ())
        geo = _geography(icp or {})
        unapplied: list[str] = []
        if geo.get("radius_km") or geo.get("radius") or geo.get("city"):
            unapplied.append("radius")
        states = geo.get("states") or []
        if isinstance(states, list) and len([s for s in states if str(s).strip()]) > 1:
            unapplied.append("multi_uf")
        return TargetingOutcome(filters, tuple(unapplied))


def _geography(icp: Mapping[str, Any]) -> Mapping[str, Any]:
    geo = (icp or {}).get("geography") or {}
    return geo if isinstance(geo, Mapping) else {}


def _prefix_token(start: str) -> str:
    """Recupera o token de prefixo a partir do início da faixa."""
    for length in range(1, 7):
        if start == start[:length] + "0" * (7 - length):
            return start[:length]
    return start


def build_search_filters(
    icp: Mapping[str, Any] | None,
    discovery: Mapping[str, Any] | None = None,
    *,
    target_candidates: int | None = None,
    limit: int | None = None,
) -> SearchFilters | None:
    """Monta `SearchFilters` ou None (Registry não deve ser consultado)."""
    del discovery  # reservado para firmographics futuros; targeting hoje é icp.
    icp = icp or {}
    try:
        cnae: CnaeFilter = parse_cnae_tokens(icp.get("cnaes") or [])
    except ValueError:
        return None
    if cnae.empty:
        return None
    geo = _geography(icp)
    states = [s for s in (geo.get("states") or []) if str(s).strip()]
    uf = str(states[0]).strip().upper() if len(states) == 1 else None
    ufs = sorted({str(state).strip().upper() for state in states}) or None
    sizes = [str(value).strip().upper() for value in (icp.get("company_sizes") or [])]
    if any(size not in PORTE_CODES for size in sizes):
        return None
    portes = list(dict.fromkeys(PORTE_CODES[size] for size in sizes)) or None
    situations = geo.get("situations") or geo.get("situacoes")
    if situations is not None and not isinstance(situations, list):
        return None
    situations = [str(value).strip() for value in (situations or []) if str(value).strip()] or None
    municipality = geo.get("municipality_code") or geo.get("municipio_cod")
    matrix = geo.get("matrix")
    if matrix is not None and not isinstance(matrix, bool):
        return None
    wanted = target_candidates if target_candidates is not None else limit
    try:
        wanted_int = int(wanted) if wanted is not None else PAGE_SIZE_DEFAULT
    except (TypeError, ValueError):
        wanted_int = PAGE_SIZE_DEFAULT
    wanted_int = max(1, min(wanted_int, PAGE_SIZE_MAX))
    return SearchFilters(
        cnaes=sorted(cnae.exact) or None,
        cnae_prefixes=sorted({_prefix_token(s) for (s, _e) in cnae.prefixes}) or None,
        uf=uf,
        ufs=ufs if len(states) > 1 else None,
        municipio_cod=str(municipality).strip() if municipality else None,
        situacoes=situations,
        matriz=matrix,
        portes=portes,
        limit=wanted_int,
    )
