"""RegistryCandidate: resultado de descoberta do universo empresarial.

Não é Company: não tem organization_id, não pertence ao CRM, não entra em
fluxo comercial sozinho. A promoção futura para Company será explícita.
`observed_at` é None porque a fonte não informa observação por registro —
só sabemos quando importamos (`imported_at`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class RegistryCandidate:
    cnpj: str
    razao_social: str | None = None
    nome_fantasia: str | None = None
    matriz: bool | None = None
    situacao: str | None = None
    data_situacao: str | None = None
    cnae_principal: str | None = None
    cnae_principal_label: str | None = None
    cnaes_secundarios: list[str] = field(default_factory=list)
    natureza_juridica: str | None = None
    porte: str | None = None
    capital_social: str | None = None
    municipio_cod: str | None = None
    uf: str | None = None
    endereco: dict[str, str | None] | None = None
    source: str = "receita_cnpj"
    source_snapshot: str | None = None
    observed_at: datetime | None = None
    imported_at: datetime | None = None
    provenance: dict[str, str | None] | None = None

    @classmethod
    def from_row(
        cls, row, *, secundarias: list[str] | None = None,
        cnae_label: str | None = None,
    ) -> "RegistryCandidate":
        return cls(
            cnpj=row.cnpj,
            razao_social=row.razao_social,
            nome_fantasia=row.nome_fantasia,
            matriz=row.matriz,
            situacao=row.situacao,
            data_situacao=row.data_situacao.isoformat() if row.data_situacao else None,
            cnae_principal=row.cnae_principal,
            cnae_principal_label=cnae_label,
            cnaes_secundarios=list(secundarias or []),
            natureza_juridica=row.natureza_juridica,
            porte=row.porte,
            capital_social=str(row.capital_social) if row.capital_social is not None else None,
            municipio_cod=row.municipio_cod,
            uf=row.uf,
            endereco={
                "tipo_logradouro": row.tipo_logradouro,
                "logradouro": row.logradouro,
                "numero": row.numero,
                "complemento": row.complemento,
                "bairro": row.bairro,
                "cep": row.cep,
            },
            source=row.source or "receita_cnpj",
            source_snapshot=row.source_snapshot,
            observed_at=None,
            imported_at=row.imported_at,
            provenance={
                "source": row.source or "receita_cnpj",
                "source_snapshot": row.source_snapshot,
            },
        )
