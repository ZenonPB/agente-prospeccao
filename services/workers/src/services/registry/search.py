"""Consulta ao universo empresarial: filtros composáveis, keyset, sem N+1.

Visibilidade por membership versionado: default enxerga o snapshot ACTIVE;
mês explícito exige snapshot COMPLETED/ACTIVE (fail-closed, sem fallback).
Sempre 3 queries no máximo (+1 de resolução só quando o mês é explícito):
página, secundários (IN), labels CNAE (IN). Ordenação determinística por
CNPJ; cursor = último CNPJ da página.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database.models import (
    RegistryCnae,
    RegistryCompany,
    RegistryCompanyCnae,
    RegistrySnapshotMember,
)
from services.registry.activation import (
    active_snapshot_id_subquery,
    resolve_snapshot_id,
)
from services.registry.candidate import RegistryCandidate
from services.registry.cnae_matching import (
    MAX_PREFIX_LEN,
    MIN_PREFIX_LEN,
    cnae_prefix_bounds,
    normalize_cnae_token,
)
from services.registry.cnpj import normalize_cnpj

from services.registry.manifest import BRAZILIAN_UF_CODES, validate_snapshot_month

PAGE_SIZE_DEFAULT = 50
PAGE_SIZE_MAX = 100

@dataclass(frozen=True)
class SearchFilters:
    cnpj: str | None = None
    cnaes: list[str] | None = None
    cnae_prefixes: list[str] | None = None
    uf: str | None = None
    ufs: list[str] | None = None
    municipio_cod: str | None = None
    situacao: str | None = None
    situacoes: list[str] | None = None
    matriz: bool | None = None
    porte: str | None = None
    portes: list[str] | None = None
    limit: int = PAGE_SIZE_DEFAULT
    cursor: str | None = None
    source_snapshot: str | None = None

    def __post_init__(self) -> None:
        if self.limit is not None and self.limit < 1:
            raise ValueError("limit deve ser positivo")
        object.__setattr__(self, "limit", min(self.limit or PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX))
        if self.cursor is not None:
            cursor = normalize_cnpj(self.cursor)
            if not cursor or len(cursor) != 14 or not (cursor.isascii() and cursor.isalnum()):
                raise ValueError(f"cursor inválido: {self.cursor!r}")
            object.__setattr__(self, "cursor", cursor)
        if self.uf is not None:
            uf = str(self.uf).strip().upper()
            if uf not in BRAZILIAN_UF_CODES:
                raise ValueError(f"UF inválida: {self.uf!r}")
            object.__setattr__(self, "uf", uf)
        if self.ufs is not None:
            normalized_ufs = [str(uf).strip().upper() for uf in self.ufs]
            if any(uf not in BRAZILIAN_UF_CODES for uf in normalized_ufs):
                raise ValueError(f"UF inválida: {self.ufs!r}")
            object.__setattr__(
                self, "ufs",
                sorted(set(normalized_ufs)) or None,
            )
        if self.cnaes is not None:
            exact: list[str] = []
            for raw in self.cnaes:
                digits = normalize_cnae_token(raw)
                if len(digits) != 7:
                    raise ValueError(f"CNAE exato inválido: {raw!r}")
                if digits not in exact:
                    exact.append(digits)
            object.__setattr__(self, "cnaes", sorted(exact) or None)
        if self.cnae_prefixes is not None:
            prefixes: list[str] = []
            for raw in self.cnae_prefixes:
                digits = normalize_cnae_token(raw)
                if not MIN_PREFIX_LEN <= len(digits) <= MAX_PREFIX_LEN:
                    raise ValueError(f"prefixo CNAE inválido: {raw!r}")
                if digits not in prefixes:
                    prefixes.append(digits)
            object.__setattr__(self, "cnae_prefixes", sorted(prefixes) or None)
        if self.situacoes is not None:
            object.__setattr__(
                self, "situacoes",
                [s.strip() for s in self.situacoes if s and s.strip()] or None)
        if self.portes is not None:
            object.__setattr__(
                self, "portes",
                [p.strip() for p in self.portes if p and p.strip()] or None)
        if self.source_snapshot is not None:
            object.__setattr__(
                self, "source_snapshot",
                validate_snapshot_month(str(self.source_snapshot).strip()))


@dataclass(frozen=True)
class SearchResult:
    items: list[RegistryCandidate] = field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False


class RegistrySearchService:
    """Queries de descoberta sobre `registry_companies` (leitura global).

    Ativação: sem mês explícito, a busca enxerga o snapshot ACTIVE —
    staging e snapshots com falha nunca vazam para descoberta. Sem ACTIVE,
    o resultado é vazio (honesto: nada publicado). Mês explícito resolve
    para o membership daquele snapshot e falha fechado quando indisponível.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def search(self, filters: SearchFilters) -> SearchResult:
        from services.registry.importer import SOURCE

        cnpj = normalize_cnpj(filters.cnpj) if filters.cnpj else None
        if filters.cnpj and not cnpj:
            return SearchResult()
        stmt = select(RegistryCompany)
        if filters.source_snapshot:
            snapshot_id = resolve_snapshot_id(
                self._db, source=SOURCE, snapshot_month=filters.source_snapshot)
            stmt = stmt.where(RegistryCompany.cnpj.in_(
                select(RegistrySnapshotMember.cnpj).where(
                    RegistrySnapshotMember.snapshot_id == snapshot_id)))
        else:
            active = active_snapshot_id_subquery(SOURCE)
            stmt = stmt.where(RegistryCompany.cnpj.in_(
                select(RegistrySnapshotMember.cnpj).where(
                    RegistrySnapshotMember.snapshot_id == active)))
        if cnpj:
            stmt = stmt.where(RegistryCompany.cnpj == cnpj)
        if filters.cnaes or filters.cnae_prefixes:
            clauses = []
            if filters.cnaes:
                clauses.append(RegistryCompany.cnae_principal.in_(filters.cnaes))
                clauses.append(RegistryCompany.cnpj.in_(
                    select(RegistryCompanyCnae.cnpj).where(
                        RegistryCompanyCnae.cnae.in_(filters.cnaes)),
                ))
            for prefix in filters.cnae_prefixes or []:
                start, end = cnae_prefix_bounds(prefix)
                clauses.append(RegistryCompany.cnae_principal.between(start, end))
                clauses.append(RegistryCompany.cnpj.in_(
                    select(RegistryCompanyCnae.cnpj).where(
                        RegistryCompanyCnae.cnae.between(start, end)),
                ))
            stmt = stmt.where(or_(*clauses))
        if filters.uf:
            stmt = stmt.where(RegistryCompany.uf == filters.uf)
        elif filters.ufs:
            stmt = stmt.where(RegistryCompany.uf.in_(filters.ufs))
        if filters.municipio_cod:
            stmt = stmt.where(RegistryCompany.municipio_cod == filters.municipio_cod)
        if filters.situacao:
            stmt = stmt.where(RegistryCompany.situacao == filters.situacao)
        elif filters.situacoes:
            stmt = stmt.where(RegistryCompany.situacao.in_(filters.situacoes))
        if filters.matriz is not None:
            stmt = stmt.where(RegistryCompany.matriz.is_(filters.matriz))
        if filters.porte:
            stmt = stmt.where(RegistryCompany.porte == filters.porte)
        elif filters.portes:
            stmt = stmt.where(RegistryCompany.porte.in_(filters.portes))
        if filters.cursor:
            stmt = stmt.where(RegistryCompany.cnpj > filters.cursor)
        stmt = stmt.order_by(RegistryCompany.cnpj).limit(filters.limit + 1)
        rows = list(self._db.execute(stmt).scalars().all())
        has_more = len(rows) > filters.limit
        page = rows[: filters.limit]
        if not page:
            return SearchResult()
        cnpjs = [r.cnpj for r in page]
        sec = self._db.execute(
            select(RegistryCompanyCnae.cnpj, RegistryCompanyCnae.cnae)
            .where(RegistryCompanyCnae.cnpj.in_(cnpjs))
            .order_by(RegistryCompanyCnae.cnpj, RegistryCompanyCnae.cnae)
        ).all()
        sec_by_cnpj: dict[str, list[str]] = {}
        for owner, code in sec:
            sec_by_cnpj.setdefault(owner, []).append(code)
        codes = {r.cnae_principal for r in page if r.cnae_principal}
        codes.update(code for codes_list in sec_by_cnpj.values() for code in codes_list)
        labels = dict(self._db.execute(
            select(RegistryCnae.codigo, RegistryCnae.descricao)
            .where(RegistryCnae.codigo.in_(sorted(codes)))
        ).all()) if codes else {}
        items = [
            RegistryCandidate.from_row(
                r, secundarias=sec_by_cnpj.get(r.cnpj, []),
                cnae_label=labels.get(r.cnae_principal) if r.cnae_principal else None,
            )
            for r in page
        ]
        return SearchResult(
            items=items,
            next_cursor=page[-1].cnpj if has_more else None,
            has_more=has_more,
        )
