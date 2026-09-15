"""Consulta ao universo empresarial: filtros composáveis, keyset, sem N+1.

Sempre 3 queries no máximo: página, secundários (IN), labels CNAE (IN).
Ordenação determinística por CNPJ; cursor = último CNPJ da página.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database.models import RegistryCnae, RegistryCompany, RegistryCompanyCnae
from services.registry.candidate import RegistryCandidate
from services.registry.cnpj import normalize_cnpj

PAGE_SIZE_DEFAULT = 50
PAGE_SIZE_MAX = 100

@dataclass(frozen=True)
class SearchFilters:
    cnpj: str | None = None
    cnaes: list[str] | None = None
    uf: str | None = None
    municipio_cod: str | None = None
    situacao: str | None = None
    matriz: bool | None = None
    porte: str | None = None
    limit: int = PAGE_SIZE_DEFAULT
    cursor: str | None = None

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
            object.__setattr__(self, "uf", self.uf.strip().upper() or None)
        if self.cnaes is not None:
            object.__setattr__(
                self, "cnaes", [c.strip() for c in self.cnaes if c and c.strip()] or None)


@dataclass(frozen=True)
class SearchResult:
    items: list[RegistryCandidate] = field(default_factory=list)
    next_cursor: str | None = None
    has_more: bool = False


class RegistrySearchService:
    """Queries de descoberta sobre `registry_companies` (leitura global)."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def search(self, filters: SearchFilters) -> SearchResult:
        cnpj = normalize_cnpj(filters.cnpj) if filters.cnpj else None
        if filters.cnpj and not cnpj:
            return SearchResult()
        stmt = select(RegistryCompany)
        if cnpj:
            stmt = stmt.where(RegistryCompany.cnpj == cnpj)
        if filters.cnaes:
            stmt = stmt.where(or_(
                RegistryCompany.cnae_principal.in_(filters.cnaes),
                RegistryCompany.cnpj.in_(
                    select(RegistryCompanyCnae.cnpj).where(
                        RegistryCompanyCnae.cnae.in_(filters.cnaes)),
                ),
            ))
        if filters.uf:
            stmt = stmt.where(RegistryCompany.uf == filters.uf)
        if filters.municipio_cod:
            stmt = stmt.where(RegistryCompany.municipio_cod == filters.municipio_cod)
        if filters.situacao:
            stmt = stmt.where(RegistryCompany.situacao == filters.situacao)
        if filters.matriz is not None:
            stmt = stmt.where(RegistryCompany.matriz.is_(filters.matriz))
        if filters.porte:
            stmt = stmt.where(RegistryCompany.porte == filters.porte)
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
