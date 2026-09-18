"""Manifesto de snapshot oficial do Registry (origem + integridade esperada).

O manifesto descreve o que o operador baixou da fonte oficial (ou de
espelho explícito) ANTES da ingestão: mês, layout, encoding, origem e, por
arquivo, tamanho e SHA-256 observados. O importer valida contra ele e
registra `layout_version` no ledger — nunca inventa proveniência.

Sem I/O de rede, sem DB, sem relógio: tudo é dado explícito. URLs oficiais
são restritas a hosts conhecidos; espelho de terceiros exige `origin_kind`
explícito e https (nunca autoridade silenciosa).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlparse

from services.registry.parser import COLUMN_COUNTS

MANIFEST_VERSION = "1"

# Hosts onde a Receita publica dados abertos do CNPJ (catálogo e arquivos).
OFFICIAL_HOSTS = frozenset({
    "arquivos.receitafederal.gov.br",
    "www.gov.br",
    "gov.br",
    "dados.gov.br",
})

OFFICIAL_KINDS = frozenset({"receita_oficial"})
MIRROR_KINDS = frozenset({"espelho_terceiros"})

# Encodings aceitos pelo leitor de snapshot (nomes do codec Python).
ENCODINGS = frozenset({"latin-1", "iso-8859-1", "utf-8", "utf-8-sig", "cp1252"})

_SNAPSHOT_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_ACCESS_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ManifestError(ValueError):
    """Manifesto malformado ou inconsistente: falhar fechado, sem importar."""


# UFs válidas do Brasil (usadas por busca, targeting e escopo de importação).
BRAZILIAN_UF_CODES = frozenset({
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO",
})


def validate_snapshot_month(value: str) -> str:
    """AAAA-MM do snapshot (ex. 2026-08). Formato inválido é erro, não dado."""
    if not _SNAPSHOT_MONTH_RE.fullmatch(value or ""):
        raise ValueError(f"snapshot_month inválido (esperado AAAA-MM): {value!r}")
    return value


@dataclass(frozen=True)
class ManifestFile:
    table_kind: str
    file_name: str
    bytes: int | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class SnapshotManifest:
    source: str
    snapshot_month: str
    layout: str
    layout_version: str
    encoding: str
    origin_kind: str
    origin_url: str
    accessed_at: str
    files: tuple[ManifestFile, ...] = field(default_factory=tuple)
    scope: Mapping[str, Any] | None = None


def _text(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"manifesto: campo obrigatório ausente: {key}")
    return value.strip()


def _validate_month(value: str) -> str:
    try:
        return validate_snapshot_month(value)
    except ValueError as exc:
        raise ManifestError(f"manifesto: {exc}") from exc


def _validate_origin(kind: str, url: str) -> tuple[str, str]:
    kind = kind.strip()
    if kind not in OFFICIAL_KINDS | MIRROR_KINDS:
        raise ManifestError(f"manifesto: origin_kind desconhecido: {kind!r}")
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ManifestError(f"manifesto: origin_url deve ser https: {url!r}")
    if kind in OFFICIAL_KINDS and parsed.hostname not in OFFICIAL_HOSTS:
        raise ManifestError(
            f"manifesto: origem oficial fora dos hosts conhecidos: {parsed.hostname!r} "
            "(use origin_kind espelho_terceiros para declarar espelho explícito)"
        )
    return kind, url.strip()


def _validate_file(entry: Any) -> ManifestFile:
    if not isinstance(entry, Mapping):
        raise ManifestError("manifesto: arquivo deve ser um objeto")
    kind = entry.get("table_kind")
    if kind not in COLUMN_COUNTS:
        raise ManifestError(f"manifesto: table_kind desconhecido: {kind!r}")
    name = entry.get("file_name")
    if not isinstance(name, str) or not name.strip():
        raise ManifestError("manifesto: file_name obrigatório")
    size = entry.get("bytes")
    if size is not None and (not isinstance(size, int) or size < 0):
        raise ManifestError(f"manifesto: bytes inválido para {name!r}")
    digest = entry.get("sha256")
    if digest is not None:
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest.strip().lower()):
            raise ManifestError(f"manifesto: sha256 inválido para {name!r}")
        digest = digest.strip().lower()
    return ManifestFile(table_kind=kind, file_name=name.strip(), bytes=size, sha256=digest)


def parse_manifest(data: Mapping[str, Any]) -> SnapshotManifest:
    """Valida um manifesto já carregado (dict). Erro vira ManifestError."""
    if not isinstance(data, Mapping):
        raise ManifestError("manifesto: raiz deve ser um objeto")
    if str(data.get("manifest_version", "")).strip() != MANIFEST_VERSION:
        raise ManifestError(
            f"manifesto: manifest_version deve ser {MANIFEST_VERSION!r}")
    raw_files = data.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise ManifestError("manifesto: files deve ser uma lista não vazia")
    files = tuple(_validate_file(entry) for entry in raw_files)
    names = [entry.file_name for entry in files]
    if len(set(names)) != len(names):
        raise ManifestError("manifesto: file_name duplicado")
    if not any(entry.table_kind == "estabelecimentos" for entry in files):
        raise ManifestError("manifesto: exige ao menos um arquivo estabelecimentos")
    encoding = _text(data, "encoding").lower()
    if encoding not in ENCODINGS:
        raise ManifestError(f"manifesto: encoding desconhecido: {encoding!r}")
    accessed_at = _text(data, "accessed_at")
    if not _ACCESS_DATE_RE.fullmatch(accessed_at):
        raise ManifestError(f"manifesto: accessed_at deve ser AAAA-MM-DD: {accessed_at!r}")
    layout_version = _text(data, "layout_version")
    if len(layout_version) > 20:
        raise ManifestError("manifesto: layout_version com mais de 20 caracteres")
    kind, url = _validate_origin(_text(data, "origin_kind"), _text(data, "origin_url"))
    scope = data.get("scope")
    if scope is not None and not isinstance(scope, Mapping):
        raise ManifestError("manifesto: scope deve ser um objeto")
    return SnapshotManifest(
        source=_text(data, "source"),
        snapshot_month=_validate_month(_text(data, "snapshot_month")),
        layout=_text(data, "layout"),
        layout_version=layout_version,
        encoding=encoding,
        origin_kind=kind,
        origin_url=url,
        accessed_at=accessed_at,
        files=files,
        scope=dict(scope) if scope is not None else None,
    )


def load_manifest(path: str) -> SnapshotManifest:
    """Lê e valida um manifesto JSON. Falha de leitura/parse vira ManifestError."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as exc:
        raise ManifestError(f"manifesto inacessível: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifesto com JSON inválido: {exc}") from exc
    return parse_manifest(data)


def dump_manifest(manifest: SnapshotManifest) -> str:
    """Serializa o manifesto em JSON canônico (chaves ordenadas)."""
    return json.dumps({
        "manifest_version": MANIFEST_VERSION,
        "source": manifest.source,
        "snapshot_month": manifest.snapshot_month,
        "layout": manifest.layout,
        "layout_version": manifest.layout_version,
        "encoding": manifest.encoding,
        "origin_kind": manifest.origin_kind,
        "origin_url": manifest.origin_url,
        "accessed_at": manifest.accessed_at,
        "files": [
            {"table_kind": entry.table_kind, "file_name": entry.file_name,
             **({"bytes": entry.bytes} if entry.bytes is not None else {}),
             **({"sha256": entry.sha256} if entry.sha256 is not None else {})}
            for entry in manifest.files
        ],
        **({"scope": manifest.scope} if manifest.scope is not None else {}),
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def find_file(manifest: SnapshotManifest, file_name: str) -> ManifestFile | None:
    """Localiza a entrada esperada de um arquivo (None quando ausente)."""
    for entry in manifest.files:
        if entry.file_name == file_name:
            return entry
    return None
