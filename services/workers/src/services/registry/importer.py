"""Ingestão idempotente e reiniciável do universo empresarial (Receita/CNPJ).

Streaming em chunks: parse → merge em temp table → upsert → checkpoint.
Nunca materializa o arquivo inteiro; cada chunk commita e avança o
checkpoint (`processed_lines`), então interromper e retomar é seguro.

Contadores do snapshot valem para a execução (última run); o histórico por
arquivo vive em `registry_import_files`. `failed` conta arquivos com falha
estrutural. Ingestão offline não consome budget de API.
"""
from __future__ import annotations

import hashlib
import itertools
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

import sqlalchemy as sa
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.models import (
    RegistryCnae,
    RegistryCompany,
    RegistryCompanyCnae,
    RegistryImportFile,
    RegistrySnapshot,
)
from services.registry.parser import COLUMN_COUNTS, RowResult, iter_records

logger = logging.getLogger(__name__)

PARSER_VERSION = "1"
SOURCE = "receita_cnpj"

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


def content_hash_for(values: dict[str, Any]) -> str:
    """Hash estável dos campos operacionais — decide updated vs unchanged."""
    parts = [f"{k}={values.get(k)}" for k in COMPANY_KEYS]
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
    values["content_hash"] = content_hash_for(values)
    return values


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
    ) -> RegistrySnapshot:
        for spec in files:
            if spec.table_kind not in COLUMN_COUNTS:
                raise ValueError(f"table_kind desconhecido: {spec.table_kind}")
        db = self._db
        snapshot = self._get_or_create_snapshot(db, source, snapshot_month)
        snapshot.status = "RUNNING"
        snapshot.finished_at = None
        snapshot.error = None
        for field in ("processed", "inserted", "updated", "unchanged", "rejected", "failed"):
            setattr(snapshot, field, 0)
        db.commit()

        totals = {"processed": 0, "inserted": 0, "updated": 0, "unchanged": 0, "rejected": 0, "failed": 0}
        for spec in files:
            counts = self._import_file(snapshot, spec)
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

    def _import_file(self, snapshot: RegistrySnapshot, spec: RegistryFileSpec) -> dict[str, int]:
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
        if row.status == "COMPLETED" and row.file_bytes == size and size is not None:
            logger.info("registry skip %s (inalterado, %s bytes)", spec.file_name, size)
            return {}
        if row.status == "COMPLETED":
            # Conteúdo mudou desde a conclusão: recomeça do zero.
            row.processed_lines = 0
            row.rows_ok = 0
            row.rows_rejected = 0
        row.status = "RUNNING"
        row.started_at = datetime.now(timezone.utc)
        row.finished_at = None
        row.error = None
        row.file_bytes = size
        if row.processed_lines is None:
            row.processed_lines = 0
        db.commit()

        counts = {"processed": 0, "inserted": 0, "updated": 0, "unchanged": 0, "rejected": 0, "failed": 0}
        start = time.perf_counter()
        warned = 0
        try:
            handle = open(spec.path, encoding=self._encoding)
        except OSError as exc:
            return self._fail_file(row, f"arquivo inacessível: {exc}")
        try:
            lines = itertools.islice(handle, row.processed_lines, None)
            chunk: list[RowResult] = []
            for result in iter_records(lines, kind=spec.table_kind):
                chunk.append(result)
                if len(chunk) >= self._batch_size:
                    warned = self._apply_chunk(snapshot, row, spec, chunk, counts, warned)
                    chunk = []
            if chunk:
                self._apply_chunk(snapshot, row, spec, chunk, counts, warned)
        except UnicodeDecodeError as exc:
            db.rollback()
            return self._fail_file(row, f"encoding inválida ({self._encoding}): {exc}")
        except Exception as exc:  # chunk falhou e já fez rollback: fail-closed
            db.rollback()
            return self._fail_file(row, f"falha no chunk: {exc}")
        finally:
            handle.close()
        row.status = "COMPLETED"
        row.finished_at = datetime.now(timezone.utc)
        db.commit()
        elapsed = max(time.perf_counter() - start, 0.001)
        logger.info(
            "registry %s ok: %d linhas em %.1fs (%.0f/s)",
            spec.file_name, counts["processed"], elapsed, counts["processed"] / elapsed,
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
    ) -> int:
        db = self._db
        ok = [r.record for r in chunk if r.ok]
        bad = [r for r in chunk if not r.ok]
        for result in bad[: max(0, 5 - warned)]:
            logger.warning("registry %s linha %d rejeitada: %s", spec.file_name, result.line_no, result.error)
        warned += min(len(bad), max(0, 5 - warned))
        now = datetime.now(timezone.utc)
        stats = {"inserted": 0, "updated": 0, "unchanged": 0}
        if ok:
            if spec.table_kind == "estabelecimentos":
                stats = self._merge_companies(snapshot, ok, now)
            elif spec.table_kind == "empresas":
                stats = self._merge_empresas(ok)
            elif spec.table_kind == "cnaes":
                stats = self._merge_cnaes(ok)
        counts["processed"] += len(ok)
        counts["rejected"] += len(bad)
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
                           "(LIKE registry_companies INCLUDING DEFAULTS) ON COMMIT DROP"))
        db.execute(tmp.insert(), [{k: v.get(k) for k in TMP_COLUMNS} for v in batch])
        inserted_ids = {r[0] for r in db.execute(
            insert(RegistryCompany).from_select(
                TMP_COLUMNS,
                select(*[tmp.c[k] for k in TMP_COLUMNS]).where(
                    ~select(1).where(RegistryCompany.cnpj == tmp.c.cnpj).exists()),
            ).on_conflict_do_nothing(index_elements=["cnpj"])
            .returning(RegistryCompany.cnpj),
        ).all()}
        updated_ids = {r[0] for r in db.execute(
            update(RegistryCompany)
            .where(RegistryCompany.cnpj == tmp.c.cnpj)
            .where(RegistryCompany.content_hash.is_distinct_from(tmp.c.content_hash))
            .values({k: tmp.c[k] for k in TMP_COLUMNS if k != "cnpj"})
            .returning(RegistryCompany.cnpj),
        ).all()}
        changed = inserted_ids | updated_ids
        if changed:
            db.execute(delete(RegistryCompanyCnae).where(RegistryCompanyCnae.cnpj.in_(sorted(changed))))
            by_cnpj = {v["cnpj"]: rec.get("cnaes_secundarios") or [] for v, rec in zip(batch, records)}
            pairs = [{"cnpj": cnpj, "cnae": code}
                     for cnpj in sorted(changed) for code in by_cnpj.get(cnpj, [])]
            if pairs:
                db.execute(insert(RegistryCompanyCnae).values(pairs).on_conflict_do_nothing())
        return {"inserted": len(inserted_ids), "updated": len(updated_ids),
                "unchanged": len(batch) - len(inserted_ids) - len(updated_ids)}

    def _merge_empresas(self, records: list[dict[str, Any]]) -> dict[str, int]:
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
            update(RegistryCompany)
            .where(RegistryCompany.cnpj_basico == tmp.c.basico)
            .where(or_(
                RegistryCompany.razao_social.is_distinct_from(tmp.c.razao),
                RegistryCompany.natureza_juridica.is_distinct_from(tmp.c.natju),
                RegistryCompany.porte.is_distinct_from(tmp.c.porte),
                RegistryCompany.capital_social.is_distinct_from(tmp.c.capital),
            ))
            .values(
                razao_social=tmp.c.razao, natureza_juridica=tmp.c.natju,
                porte=tmp.c.porte, capital_social=tmp.c.capital,
                updated_at=func.now(),
            )
        ).rowcount or 0
        return {"inserted": 0, "updated": updated, "unchanged": len(records) - updated}

    def _merge_cnaes(self, records: list[dict[str, Any]]) -> dict[str, int]:
        # Referência é insert-only (labels quase imutáveis; correções futuras
        # entram por migração dedicada, não por reimport).
        db = self._db
        inserted = 0
        for rec in records:
            res = db.execute(
                insert(RegistryCnae).values(codigo=rec["codigo"], descricao=rec["descricao"])
                .on_conflict_do_nothing(index_elements=["codigo"]))
            inserted += res.rowcount or 0
        return {"inserted": inserted, "updated": 0, "unchanged": len(records) - inserted}
