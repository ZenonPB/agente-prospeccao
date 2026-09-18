"""Ingestão idempotente e reiniciável do universo empresarial (Receita/CNPJ).

Streaming em chunks: parse → staging (`registry_staging_*`) → checkpoint.
Nunca materializa o arquivo inteiro; cada chunk commita e avança o
checkpoint (`processed_lines`), então interromper e retomar é seguro.

O importer NUNCA escreve no canônico (`registry_companies`): linhas vão
para staging invisível e só viram visíveis via `activate_snapshot`
(transação única). Snapshot com falha não altera o ACTIVE anterior.
Membership é gravado por observação — linhas inalteradas continuam
pertencendo ao snapshot novo.

Identidade do arquivo: tamanho NÃO é identidade. O skip de arquivo concluído
exige digest SHA-256 igual; tamanhos iguais com bytes diferentes reprocessam.
O digest é calculado em streaming (sem segunda leitura no caminho normal).

Contadores do snapshot valem para a execução (última run); o histórico por
arquivo vive em `registry_import_files`. `failed` conta arquivos com falha
estrutural. Ingestão offline não consome budget de API.
"""
from __future__ import annotations

import codecs
import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, BinaryIO, Iterator, Sequence

import sqlalchemy as sa
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import (
    RegistryCnae,
    RegistryCompany,
    RegistrySnapshot,
    RegistryStagingCompany,
    RegistryStagingCompanyCnae,
    RegistrySnapshotMember,
)
from services.registry.manifest import (
    ManifestFile,
    SnapshotManifest,
    find_file,
    validate_snapshot_month,
)
from services.registry.parser import COLUMN_COUNTS, RowResult, iter_records
from services.registry.scope import ImportScope, scope_matches

logger = logging.getLogger(__name__)

PARSER_VERSION = "1"
SOURCE = "receita_cnpj"

# Ordem canônica de aplicação: estabelecimentos criam as linhas; empresas
# enriquecem por base; referências são independentes. O CLI aceita qualquer
# ordem — o importer normaliza para não depender do operador.
_KIND_ORDER = {"estabelecimentos": 0, "empresas": 1, "cnaes": 2}


COMPANY_KEYS = (
    "cnpj", "cnpj_basico", "razao_social", "nome_fantasia", "matriz",
    "situacao", "data_situacao", "motivo_situacao", "cidade_exterior",
    "pais_cod", "data_inicio", "cnae_principal", "natureza_juridica",
    "porte", "capital_social", "tipo_logradouro", "logradouro", "numero",
    "complemento", "bairro", "cep", "uf", "municipio_cod",
    "situacao_especial", "data_situacao_especial",
)
TMP_COLUMNS = list(COMPANY_KEYS) + ["content_hash", "source", "source_snapshot", "updated_at"]


@dataclass(frozen=True)
class RegistryFileSpec:
    table_kind: str
    path: str
    file_name: str


def content_hash_for(values: dict[str, Any], *, secundarias: Sequence[str] = ()) -> str:
    """Hash estável da identidade operacional: campos + secundários ordenados."""
    parts = [f"{k}={values.get(k)}" for k in COMPANY_KEYS]
    parts.append(f"secundarias={','.join(sorted(secundarias))}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def company_values(
    record: dict[str, Any], *, source: str, snapshot_month: str, now: datetime,
) -> dict[str, Any]:
    values = {k: record.get(k) for k in COMPANY_KEYS}
    values.update({
        "razao_social": None,
        "natureza_juridica": None,
        "porte": None,
        "capital_social": None,
        "source": source,
        "source_snapshot": snapshot_month,
        "updated_at": now,
    })
    values["content_hash"] = content_hash_for(values, secundarias=record.get("cnaes_secundarios") or [])
    return values


class HashedReader:
    """Lê texto linha a linha acumulando SHA-256 dos bytes crus (streaming)."""

    def __init__(self, path: str, encoding: str) -> None:
        self._handle: BinaryIO = open(path, "rb")
        self._decoder = codecs.getincrementaldecoder(encoding)()
        self._digest = hashlib.sha256()
        self._buffer = ""
        self._exhausted = False

    def _decode(self, raw: bytes, *, final: bool = False) -> str:
        try:
            return self._decoder.decode(raw, final=final)
        except UnicodeDecodeError as exc:
            raise _UnreadableFile(f"encoding inválida: {exc}") from exc

    def __iter__(self) -> Iterator[str]:
        while True:
            newline = self._buffer.find("\n")
            if newline >= 0:
                line = self._buffer[:newline]
                self._buffer = self._buffer[newline + 1:]
                yield line.rstrip("\r")
                continue
            if self._exhausted:
                if self._buffer:
                    line, self._buffer = self._buffer, ""
                    yield line.rstrip("\r")
                return
            raw = self._handle.read(1024 * 1024)
            if not raw:
                self._exhausted = True
                tail = self._decode(b"", final=True)
                if tail:
                    self._buffer += tail
                continue
            self._digest.update(raw)
            self._buffer += self._decode(raw)

    @property
    def hexdigest(self) -> str:
        return self._digest.hexdigest()

    def close(self) -> None:
        self._handle.close()


class _UnreadableFile(Exception):
    pass


def hash_file_bytes(path: str) -> str:
    """Digest só-leitura (verificação de skip): sem parse, sem DB."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            raw = handle.read(1024 * 1024)
            if not raw:
                break
            digest.update(raw)
    return digest.hexdigest()


class RegistryImporter:
    """Importa arquivos do snapshot com ledger, checkpoint e contadores."""

    def __init__(self, db: Session, *, batch_size: int = 5000, encoding: str = "latin-1") -> None:
        if batch_size < 1:
            raise ValueError("batch_size deve ser positivo")
        self._db = db
        self._batch_size = batch_size
        self._encoding = encoding

    def import_snapshot(
        self, *, source: str = SOURCE, snapshot_month: str,
        files: Sequence[RegistryFileSpec],
        manifest: SnapshotManifest | None = None,
        scope: ImportScope | None = None,
    ) -> RegistrySnapshot:
        validate_snapshot_month(snapshot_month)
        for spec in files:
            if spec.table_kind not in COLUMN_COUNTS:
                raise ValueError(f"table_kind desconhecido: {spec.table_kind}")
        if manifest is not None:
            if manifest.snapshot_month != snapshot_month:
                raise ValueError(
                    f"manifesto de {manifest.snapshot_month} "
                    f"não corresponde ao snapshot {snapshot_month}")
            if codecs.lookup(manifest.encoding).name != codecs.lookup(self._encoding).name:
                raise ValueError(
                    f"encoding do manifesto ({manifest.encoding}) diverge "
                    f"do importer ({self._encoding})")
        ordered = sorted(files, key=lambda spec: _KIND_ORDER.get(spec.table_kind, 99))
        db = self._db
        snapshot = self._get_or_create_snapshot(db, source, snapshot_month)
        snapshot.status = "RUNNING"
        snapshot.finished_at = None
        snapshot.error = None
        if manifest is not None:
            snapshot.layout_version = manifest.layout_version
        for field in ("processed", "inserted", "updated", "unchanged", "rejected", "failed"):
            setattr(snapshot, field, 0)
        db.commit()

        totals = {"processed": 0, "inserted": 0, "updated": 0, "unchanged": 0, "rejected": 0, "failed": 0}
        for spec in ordered:
            expected = find_file(manifest, spec.file_name) if manifest is not None else None
            counts = self._import_file(snapshot, spec, expected, scope)
            for key in totals:
                totals[key] += counts.get(key, 0)
        for key, value in totals.items():
            setattr(snapshot, key, value)
        snapshot.status = "FAILED" if totals["failed"] else "COMPLETED"
        snapshot.finished_at = datetime.now(timezone.utc)
        snapshot.parser_version = PARSER_VERSION
        db.commit()
        db.refresh(snapshot)
        return snapshot

    @staticmethod
    def _get_or_create_snapshot(db: Session, source: str, snapshot_month: str) -> RegistrySnapshot:
        snapshot = db.query(RegistrySnapshot).filter(
            RegistrySnapshot.source == source,
            RegistrySnapshot.snapshot_month == snapshot_month,
        ).first()
        if snapshot is not None:
            return snapshot
        snapshot = RegistrySnapshot(source=source, snapshot_month=snapshot_month, status="RUNNING")
        db.add(snapshot)
        try:
            db.flush()
        except IntegrityError:  # outro worker criou primeiro: usa a linha vencedora
            db.rollback()
            snapshot = db.query(RegistrySnapshot).filter(
                RegistrySnapshot.source == source,
                RegistrySnapshot.snapshot_month == snapshot_month,
            ).one()
        return snapshot

    def _import_file(
        self, snapshot: RegistrySnapshot, spec: RegistryFileSpec,
        expected: ManifestFile | None = None, scope: ImportScope | None = None,
    ) -> dict[str, int]:
        db = self._db
        row = db.query(RegistryImportFile).filter(
            RegistryImportFile.snapshot_id == snapshot.id,
            RegistryImportFile.file_name == spec.file_name,
        ).first()
        if row is None:
            row = RegistryImportFile(
                snapshot_id=snapshot.id, table_kind=spec.table_kind,
                file_name=spec.file_name, status="PENDING",
            )
            db.add(row)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                row = db.query(RegistryImportFile).filter(
                    RegistryImportFile.snapshot_id == snapshot.id,
                    RegistryImportFile.file_name == spec.file_name,
                ).one()
        try:
            import os

            size = os.path.getsize(spec.path)
        except OSError as exc:
            return self._fail_file(row, f"arquivo inacessível: {exc}")
        if row.status == "COMPLETED":
            if row.sha256 and size == row.file_bytes:
                try:
                    current = hash_file_bytes(spec.path)
                except OSError as exc:
                    return self._fail_file(row, f"arquivo inacessível: {exc}")
                if current == row.sha256:
                    logger.info("registry skip %s (sha256 igual)", spec.file_name)
                    return {}
            # Conteúdo novo (ou sem digest legado): recomeça do zero.
            row.processed_lines = 0
            row.rows_ok = 0
            row.rows_rejected = 0
            row.sha256 = None
        row.status = "RUNNING"
        row.started_at = datetime.now(timezone.utc)
        row.finished_at = None
        row.error = None
        row.file_bytes = size
        if expected is not None and expected.bytes is not None and size != expected.bytes:
            return self._fail_file(
                row, f"tamanho divergente do manifesto: {size} != {expected.bytes}")
        if row.processed_lines is None:
            row.processed_lines = 0
        db.commit()

        counts = {"processed": 0, "inserted": 0, "updated": 0, "unchanged": 0, "rejected": 0, "failed": 0}
        start = time.perf_counter()
        warned = 0
        checkpoint = row.processed_lines or 0
        try:
            reader = HashedReader(spec.path, self._encoding)
        except OSError as exc:
            return self._fail_file(row, f"arquivo inacessível: {exc}")
        try:
            chunk: list[RowResult] = []
            raw_no = 0
            for line in reader:
                raw_no += 1
                if raw_no <= checkpoint:
                    continue
                for result in iter_records([line], kind=spec.table_kind):
                    result = RowResult(
                        ok=result.ok, line_no=raw_no,
                        record=result.record, error=result.error)
                    chunk.append(result)
                    if len(chunk) >= self._batch_size:
                        warned = self._apply_chunk(snapshot, row, spec, chunk, counts, warned, scope)
                        chunk = []
            if chunk:
                self._apply_chunk(snapshot, row, spec, chunk, counts, warned, scope)
        except _UnreadableFile as exc:
            db.rollback()
            return self._fail_file(row, f"{exc} ({self._encoding})")
        except Exception as exc:  # chunk falhou e já fez rollback: fail-closed
            db.rollback()
            return self._fail_file(row, f"falha no chunk: {exc}")
        finally:
            reader.close()
        row.status = "COMPLETED"
        row.finished_at = datetime.now(timezone.utc)
        row.sha256 = reader.hexdigest
        if expected is not None and expected.sha256 is not None and row.sha256 != expected.sha256:
            # Backstop de auditoria: o gate pré-importação pertence ao
            # downloader; aqui o arquivo jamais é marcado como válido.
            return self._fail_file(row, "sha256 divergente do manifesto")
        db.commit()
        elapsed = max(time.perf_counter() - start, 0.001)
        filtered = counts.get("filtered", 0)
        logger.info(
            "registry %s ok: %d linhas em %.1fs (%.0f/s)%s",
            spec.file_name, counts["processed"], elapsed, counts["processed"] / elapsed,
            f" filtradas={filtered}" if filtered else "",
        )
        return counts

    def _fail_file(self, row: RegistryImportFile, error: str) -> dict[str, int]:
        row.status = "FAILED"
        row.finished_at = datetime.now(timezone.utc)
        row.error = error[:2000]
        self._db.commit()
        logger.error("registry %s falhou: %s", row.file_name, error)
        return {"failed": 1}

    def _apply_chunk(
        self, snapshot: RegistrySnapshot, row: RegistryImportFile,
        spec: RegistryFileSpec, chunk: list[RowResult],
        counts: dict[str, int], warned: int,
        scope: ImportScope | None = None,
    ) -> int:
        db = self._db
        ok = [r.record for r in chunk if r.ok]
        bad = [r for r in chunk if not r.ok]
        for result in bad[: max(0, 5 - warned)]:
            logger.warning("registry %s linha %d rejeitada: %s", spec.file_name, result.line_no, result.error)
        warned += min(len(bad), max(0, 5 - warned))
        # O escopo filtra estabelecimentos (única tabela com geografia/CNAE);
        # empresas/cnaes enriquecem o que já existe. Fora do escopo nunca
        # toca as tabelas, mas avança o checkpoint normalmente.
        filtered = 0
        matched = ok
        if scope is not None and spec.table_kind == "estabelecimentos":
            matched = [record for record in ok if scope_matches(scope, record)]
            filtered = len(ok) - len(matched)
        now = datetime.now(timezone.utc)
        stats = {"inserted": 0, "updated": 0, "unchanged": 0}
        if matched:
            if spec.table_kind == "estabelecimentos":
                stats = self._merge_companies(snapshot, matched, now)
            elif spec.table_kind == "empresas":
                stats = self._merge_empresas(matched, snapshot)
            elif spec.table_kind == "cnaes":
                stats = self._merge_cnaes(matched)
        counts["processed"] += len(ok)
        counts["rejected"] += len(bad)
        counts["filtered"] = counts.get("filtered", 0) + filtered
        for key in ("inserted", "updated", "unchanged"):
            counts[key] += stats.get(key, 0)
        row.processed_lines = (row.processed_lines or 0) + len(chunk)
        row.rows_ok = (row.rows_ok or 0) + len(ok)
        row.rows_rejected = (row.rows_rejected or 0) + len(bad)
        db.commit()
        return warned

    def _merge_companies(
        self, snapshot: RegistrySnapshot, records: list[dict[str, Any]], now: datetime,
    ) -> dict[str, int]:
        """Grava o chunk em staging (invisível) + membership por observação.

        Contadores comparam com o conteúdo vigente (staging deste snapshot,
        senão canônico — só leitura): inserted = CNPJ novo, updated = hash
        divergente, unchanged = idêntico. O canônico só muda na ativação.
        """
        db = self._db
        batch = [company_values(r, source=snapshot.source, snapshot_month=snapshot.snapshot_month, now=now)
                 for r in records]
        tmp = sa.Table(
            "tmp_registry_load", sa.MetaData(),
            sa.Column("cnpj", sa.String(14)), sa.Column("cnpj_basico", sa.String(8)),
            sa.Column("razao_social", sa.Text), sa.Column("nome_fantasia", sa.Text),
            sa.Column("matriz", sa.Boolean), sa.Column("situacao", sa.String(2)),
            sa.Column("data_situacao", sa.Date), sa.Column("motivo_situacao", sa.String(10)),
            sa.Column("cidade_exterior", sa.Text), sa.Column("pais_cod", sa.String(3)),
            sa.Column("data_inicio", sa.Date), sa.Column("cnae_principal", sa.String(7)),
            sa.Column("natureza_juridica", sa.String(4)), sa.Column("porte", sa.String(2)),
            sa.Column("capital_social", sa.Numeric(16, 2)), sa.Column("tipo_logradouro", sa.Text),
            sa.Column("logradouro", sa.Text), sa.Column("numero", sa.Text),
            sa.Column("complemento", sa.Text), sa.Column("bairro", sa.Text),
            sa.Column("cep", sa.String(8)), sa.Column("uf", sa.String(2)),
            sa.Column("municipio_cod", sa.String(10)), sa.Column("situacao_especial", sa.Text),
            sa.Column("data_situacao_especial", sa.Date), sa.Column("content_hash", sa.String(64)),
            sa.Column("source", sa.String(40)), sa.Column("source_snapshot", sa.String(7)),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
        )
        db.execute(sa.text("CREATE TEMPORARY TABLE tmp_registry_load "
                           "(LIKE registry_staging_companies INCLUDING DEFAULTS) ON COMMIT DROP"))
        staged_cols = ["snapshot_id"] + TMP_COLUMNS
        db.execute(tmp.insert(), [
            {"snapshot_id": snapshot.id, **{k: v.get(k) for k in TMP_COLUMNS}}
            for v in batch
        ])
        # Contadores ANTES do upsert: vigente = staging deste snapshot,
        # senão canônico. Reimport do mesmo mês continua unchanged.
        chunk_cnpjs_for_stats = [v["cnpj"] for v in batch]
        staged_hashes = dict(db.execute(
            select(RegistryStagingCompany.cnpj, RegistryStagingCompany.content_hash).where(
                RegistryStagingCompany.snapshot_id == snapshot.id,
                RegistryStagingCompany.cnpj.in_(chunk_cnpjs_for_stats))
        ).all()) if batch else {}
        canonical_hashes = dict(db.execute(
            select(RegistryCompany.cnpj, RegistryCompany.content_hash).where(
                RegistryCompany.cnpj.in_(
                    [c for c in chunk_cnpjs_for_stats if c not in staged_hashes]))
        ).all()) if batch else {}
        current = {**canonical_hashes, **staged_hashes}
        inserted = sum(1 for v in batch if v["cnpj"] not in current)
        updated = sum(1 for v in batch
                      if v["cnpj"] in current
                      and (current[v["cnpj"]] or "") != (v["content_hash"] or ""))
        upsert = insert(RegistryStagingCompany).from_select(
            staged_cols,
            select(*[tmp.c[k] for k in staged_cols]),
        )
        db.execute(upsert.on_conflict_do_update(
            index_elements=["snapshot_id", "cnpj"],
            set_={k: upsert.excluded[k] for k in TMP_COLUMNS if k != "cnpj"},
        ))
        by_cnpj = {v["cnpj"]: rec.get("cnaes_secundarios") or [] for v, rec in zip(batch, records)}
        chunk_cnpjs = sorted(by_cnpj)
        db.execute(delete(RegistryStagingCompanyCnae).where(
            RegistryStagingCompanyCnae.snapshot_id == snapshot.id,
            RegistryStagingCompanyCnae.cnpj.in_(chunk_cnpjs)))
        pairs = [{"snapshot_id": snapshot.id, "cnpj": cnpj, "cnae": code}
                 for cnpj in chunk_cnpjs for code in by_cnpj.get(cnpj, [])]
        if pairs:
            db.execute(insert(RegistryStagingCompanyCnae).values(pairs).on_conflict_do_nothing())
        db.execute(
            insert(RegistrySnapshotMember).values([
                {"snapshot_id": snapshot.id, "cnpj": v["cnpj"]} for v in batch
            ]).on_conflict_do_nothing(index_elements=["snapshot_id", "cnpj"])
        )
        return {"inserted": inserted, "updated": updated,
                "unchanged": len(batch) - inserted - updated}

    def _merge_empresas(self, records: list[dict[str, Any]], snapshot: RegistrySnapshot) -> dict[str, int]:
        """Enriquece o staging do snapshot (nunca o canônico).

        Só linhas já observadas neste snapshot são enriquecidas: bases fora
        do escopo/membership do snapshot não são tocadas (diferença honesta
        em relação ao merge in-place anterior, que atualizava o canônico).
        """
        db = self._db
        tmp = sa.Table(
            "tmp_registry_emp", sa.MetaData(),
            sa.Column("basico", sa.Text), sa.Column("razao", sa.Text),
            sa.Column("natju", sa.Text), sa.Column("porte", sa.Text),
            sa.Column("capital", sa.Numeric(16, 2)),
        )
        db.execute(sa.text("CREATE TEMPORARY TABLE tmp_registry_emp "
                           "(basico TEXT, razao TEXT, natju TEXT, porte TEXT, "
                           "capital NUMERIC(16,2)) ON COMMIT DROP"))
        db.execute(tmp.insert(), [
            {"basico": r["cnpj_basico"], "razao": r["razao_social"],
             "natju": r["natureza_juridica"], "porte": r["porte"],
             "capital": r["capital_social"]}
            for r in records
        ])
        updated = db.execute(
            update(RegistryStagingCompany)
            .where(RegistryStagingCompany.snapshot_id == snapshot.id)
            .where(RegistryStagingCompany.cnpj_basico == tmp.c.basico)
            .where(or_(
                RegistryStagingCompany.razao_social.is_distinct_from(tmp.c.razao),
                RegistryStagingCompany.natureza_juridica.is_distinct_from(tmp.c.natju),
                RegistryStagingCompany.porte.is_distinct_from(tmp.c.porte),
                RegistryStagingCompany.capital_social.is_distinct_from(tmp.c.capital),
            ))
            .values(
                razao_social=tmp.c.razao, natureza_juridica=tmp.c.natju,
                porte=tmp.c.porte, capital_social=tmp.c.capital,
                source_snapshot=snapshot.snapshot_month,
                updated_at=func.now(),
            )
        ).rowcount or 0
        return {"inserted": 0, "updated": updated, "unchanged": len(records) - updated}

    def _merge_cnaes(self, records: list[dict[str, Any]]) -> dict[str, int]:
        db = self._db
        tmp = sa.Table(
            "tmp_registry_cnae", sa.MetaData(),
            sa.Column("codigo", sa.Text), sa.Column("descricao", sa.Text),
        )
        db.execute(sa.text("CREATE TEMPORARY TABLE tmp_registry_cnae "
                           "(codigo TEXT, descricao TEXT) ON COMMIT DROP"))
        db.execute(tmp.insert(), [
            {"codigo": r["codigo"], "descricao": r["descricao"]} for r in records])
        inserted = db.execute(
            insert(RegistryCnae).from_select(
                ["codigo", "descricao"],
                select(tmp.c.codigo, tmp.c.descricao).where(
                    ~select(1).where(RegistryCnae.codigo == tmp.c.codigo).exists()),
            ).on_conflict_do_nothing(index_elements=["codigo"])
            .returning(RegistryCnae.codigo),
        ).all()
        updated = db.execute(
            update(RegistryCnae)
            .where(RegistryCnae.codigo == tmp.c.codigo)
            .where(RegistryCnae.descricao.is_distinct_from(tmp.c.descricao))
            .values(descricao=tmp.c.descricao)
            .returning(RegistryCnae.codigo),
        ).all()
        return {"inserted": len(inserted), "updated": len(updated),
                "unchanged": len(records) - len(inserted) - len(updated)}
