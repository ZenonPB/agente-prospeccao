"""Escopo de importação do Registry (materialização parcial de snapshot).

Um snapshot oficial é nacional; o piloto materializa só o recorte
operacional (UF, município, CNAE, situação). O filtro roda sobre o registro
já parseado, antes do merge: linhas fora do escopo nunca tocam as tabelas,
mas continuam contando no checkpoint (retomada por linha bruta).

Sem I/O, sem DB, sem relógio. A semântica de CNAE é a mesma da busca
(`cnae_matching`): 7 dígitos exato, 2–6 prefixo ancorado.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from services.registry.cnae_matching import CnaeFilter, parse_cnae_tokens
from services.registry.manifest import BRAZILIAN_UF_CODES


@dataclass(frozen=True)
class ImportScope:
    ufs: frozenset[str] = frozenset()
    municipio_cods: frozenset[str] = frozenset()
    cnaes: frozenset[str] = frozenset()
    cnae_prefix_ranges: tuple[tuple[str, str], ...] = ()
    situacoes: frozenset[str] = frozenset()
    matriz: bool | None = None

    @property
    def empty(self) -> bool:
        return not (self.ufs or self.municipio_cods or self.cnaes
                    or self.cnae_prefix_ranges or self.situacoes
                    or self.matriz is not None)

    def to_dict(self) -> dict[str, Any]:
        """Serialização canônica do recorte (chaves ordenadas, JSON-safe)."""
        return {
            "ufs": sorted(self.ufs),
            "municipio_cods": sorted(self.municipio_cods),
            "cnaes": sorted(self.cnaes),
            "cnae_prefix_ranges": [list(pair) for pair in self.cnae_prefix_ranges],
            "situacoes": sorted(self.situacoes),
            "matriz": self.matriz,
        }


def _situacao(value: object) -> str:
    return str(value or "").strip().lstrip("0") or "0"


def parse_scope(
    *, ufs: Iterable[object] = (), municipio_cods: Iterable[object] = (),
    cnaes: Iterable[object] | None = None, situacoes: Iterable[object] = (),
    matriz: bool | None = None,
) -> ImportScope | None:
    """Monta o escopo ou None (sem restrição: importa tudo).

    UF inválida e CNAE inválido levantam ValueError (fail-closed).
    """
    states = [str(value).strip().upper() for value in (ufs or []) if str(value).strip()]
    if any(state not in BRAZILIAN_UF_CODES for state in states):
        raise ValueError(f"UF inválida: {list(ufs or [])!r}")
    municipios = frozenset(
        str(value).strip() for value in (municipio_cods or []) if str(value).strip())
    cnae_filter: CnaeFilter = parse_cnae_tokens(list(cnaes or []))
    situations = frozenset(
        _situacao(value) for value in (situacoes or []) if str(value).strip())
    if matriz is not None and not isinstance(matriz, bool):
        raise ValueError(f"matriz deve ser bool: {matriz!r}")
    scope = ImportScope(
        ufs=frozenset(states),
        municipio_cods=municipios,
        cnaes=frozenset(cnae_filter.exact),
        cnae_prefix_ranges=cnae_filter.prefixes,
        situacoes=situations,
        matriz=matriz,
    )
    return None if scope.empty else scope


def _cnae_match(scope: ImportScope, record: Mapping[str, Any]) -> bool:
    if not scope.cnaes and not scope.cnae_prefix_ranges:
        return True
    candidates = [record.get("cnae_principal"), *(record.get("cnaes_secundarios") or [])]
    for code in candidates:
        text = str(code or "").strip()
        if not text:
            continue
        if text in scope.cnaes:
            return True
        if any(start <= text <= end for start, end in scope.cnae_prefix_ranges):
            return True
    return False


def scope_matches(scope: ImportScope, record: Mapping[str, Any]) -> bool:
    """Registro parseado pertence ao escopo?"""
    uf = str(record.get("uf") or "").strip().upper()
    if scope.ufs and uf not in scope.ufs:
        return False
    municipio = str(record.get("municipio_cod") or "").strip()
    if scope.municipio_cods and municipio not in scope.municipio_cods:
        return False
    if scope.situacoes and _situacao(record.get("situacao")) not in scope.situacoes:
        return False
    if scope.matriz is not None and record.get("matriz") is not scope.matriz:
        return False
    return _cnae_match(scope, record)
