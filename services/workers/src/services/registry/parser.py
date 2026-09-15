"""Parser das linhas do layout aberto da Receita (dados públicos CNPJ).

Layout oficial: "NOVOLAYOUTDOSDADOSABERTOSDOCNPJ" (gov.br).
Físico: separador `;`, aspas `"`, sem cabeçalho, encoding por snapshot
(historicamente ISO-8859-1 — o chamador abre o arquivo e entrega texto).

O parser valida forma (nº de colunas, CNPJ válido). Contato da PJ
(e-mail/telefones/fax) é descartado aqui por minimização de dados.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Iterator

from services.registry.cnpj import is_valid_cnpj, normalize_cnpj

COLUMN_COUNTS = {
    "estabelecimentos": 30,
    "empresas": 7,
    "cnaes": 2,
}


@dataclass(frozen=True)
class RowResult:
    ok: bool
    line_no: int
    record: dict[str, Any] | None = None
    error: str | None = None


def iter_records(lines: Iterable[str], *, kind: str) -> Iterator[RowResult]:
    """Gera um RowResult por linha; erro de linha nunca aborta o lote."""
    if kind not in COLUMN_COUNTS:
        raise ValueError(f"kind desconhecido: {kind}")
    expected = COLUMN_COUNTS[kind]
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            cols = next(csv.reader([line], delimiter=";", quotechar='"'))
        except csv.Error as exc:
            yield RowResult(ok=False, line_no=line_no, error=f"linha malformada: {exc}")
            continue
        if len(cols) != expected:
            yield RowResult(
                ok=False, line_no=line_no,
                error=f"colunas inesperadas: {len(cols)} (esperado {expected})",
            )
            continue
        try:
            if kind == "estabelecimentos":
                record = _parse_estabelecimento(cols)
            elif kind == "empresas":
                record = _parse_empresa(cols)
            else:
                record = {"codigo": _text(cols[0]), "descricao": _text(cols[1])}
        except _RowRejected as exc:
            yield RowResult(ok=False, line_no=line_no, error=str(exc))
            continue
        yield RowResult(ok=True, line_no=line_no, record=record)


class _RowRejected(Exception):
    pass


def _text(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _aaaammdd(value: str | None) -> date | None:
    text = "".join(ch for ch in (value or "") if ch.isdigit())
    if len(text) != 8 or set(text) == {"0"}:
        return None
    try:
        return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None


def _capital(value: str | None) -> Decimal | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return Decimal(text.replace(".", "").replace(",", ".")) if "," in text else Decimal(text)
    except InvalidOperation:
        return None


def _cnpj(basico: str, ordem: str, dv: str) -> str:
    normalized = normalize_cnpj(f"{basico or ''}{ordem or ''}{dv or ''}")
    if not is_valid_cnpj(normalized):
        raise _RowRejected(f"cnpj inválido: {(basico or '')}/{(ordem or '')}-{(dv or '')}")
    assert normalized is not None
    return normalized


def _secundarios(value: str | None) -> list[str]:
    seen: list[str] = []
    for token in (value or "").split(","):
        code = token.strip()
        if code and code not in seen:
            seen.append(code)
    return seen


def _parse_estabelecimento(cols: list[str]) -> dict[str, Any]:
    cnpj = _cnpj(cols[0].strip(), cols[1].strip(), cols[2].strip())
    matriz_raw = cols[3].strip()
    return {
        "cnpj": cnpj,
        "cnpj_basico": cols[0].strip(),
        "matriz": True if matriz_raw == "1" else False if matriz_raw == "2" else None,
        "nome_fantasia": _text(cols[4]),
        "situacao": _text(cols[5]),
        "data_situacao": _aaaammdd(cols[6]),
        "motivo_situacao": _text(cols[7]),
        "cidade_exterior": _text(cols[8]),
        "pais_cod": _text(cols[9]),
        "data_inicio": _aaaammdd(cols[10]),
        "cnae_principal": _text(cols[11]),
        "cnaes_secundarios": _secundarios(cols[12]),
        "tipo_logradouro": _text(cols[13]),
        "logradouro": _text(cols[14]),
        "numero": _text(cols[15]),
        "complemento": _text(cols[16]),
        "bairro": _text(cols[17]),
        "cep": _text(cols[18]),
        "uf": (_text(cols[19]) or "").upper() or None,
        "municipio_cod": _text(cols[20]),
        "situacao_especial": _text(cols[28]),
        "data_situacao_especial": _aaaammdd(cols[29]),
    }


def _parse_empresa(cols: list[str]) -> dict[str, Any]:
    basico = cols[0].strip()
    if not basico:
        raise _RowRejected("cnpj básico ausente")
    return {
        "cnpj_basico": basico,
        "razao_social": _text(cols[1]),
        "natureza_juridica": _text(cols[2]),
        "qualificacao_responsavel": _text(cols[3]),
        "capital_social": _capital(cols[4]),
        "porte": _text(cols[5]),
        "ente_federativo": _text(cols[6]),
    }
