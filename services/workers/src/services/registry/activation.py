"""Ativação atômica de snapshots do Registry (membership versionado + ACTIVE).

Contrato:
- COMPLETED = carga válida, elegível, ainda invisível;
- ACTIVE = universo servido pela descoberta padrão (um por source, garantido
  por índice único parcial + transação);
- import escreve em staging e nunca toca o canônico; `activate_snapshot`
  aplica staging → canônico + membership + flip em transação única;
- falha em qualquer etapa preserva o ACTIVE anterior integralmente.
"""
from __future__ import annotations

import logging
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


class SnapshotActivationError(RuntimeError):
    """Ativação recusada ou revertida. O ACTIVE anterior segue valendo."""

    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason
        self.message = message


class SnapshotNotAvailable(ValueError):
    """Mês explícito sem snapshot utilizável (ausente, RUNNING ou FAILED)."""


_APPLY_COLUMNS = (
    "cnpj", "cnpj_basico", "razao_social", "nome_fantasia", "matriz",
    "situacao", "data_situacao", "motivo_situacao", "cidade_exterior",
    "pais_cod", "data_inicio", "cnae_principal", "natureza_juridica",
    "porte", "capital_social", "tipo_logradouro", "logradouro", "numero",
    "complemento", "bairro", "cep", "uf", "municipio_cod",
    "situacao_especial", "data_situacao_especial", "content_hash",
    "source", "source_snapshot", "imported_at", "updated_at",
)
# `imported_at` registra a primeira observação e não é reescrito em reativação.
_UPDATE_COLUMNS = tuple(c for c in _APPLY_COLUMNS if c not in ("cnpj", "imported_at"))


def get_active_snapshot(db: Any, *, source: str) -> Any | None:
    """Devolve a linha ACTIVE da source, ou None quando não há."""
    from database.models import RegistrySnapshot

    return db.query(RegistrySnapshot).filter(
        RegistrySnapshot.source == source,
        RegistrySnapshot.is_active.is_(True),
    ).one_or_none()


def resolve_snapshot(db: Any, *, source: str, snapshot_month: str | None) -> Any | None:
    """Resolve a linha do snapshot a consultar: ACTIVE (default) ou explícito.

    Mês explícito exige snapshot COMPLETED ou ACTIVE; qualquer outro estado
    falha fechado (sem fallback silencioso para o ativo).
    """
    from database.models import RegistrySnapshot

    if snapshot_month is None:
        return get_active_snapshot(db, source=source)
    row = db.query(RegistrySnapshot).filter(
        RegistrySnapshot.source == source,
        RegistrySnapshot.snapshot_month == snapshot_month,
    ).one_or_none()
    if row is None or row.status not in ("COMPLETED", "ACTIVE"):
        raise SnapshotNotAvailable(
            f"snapshot {source}/{snapshot_month} indisponível para consulta")
    return row


def resolve_snapshot_id(db: Any, *, source: str, snapshot_month: str | None) -> Any | None:
    """Id de `resolve_snapshot` (None quando não há ACTIVE e mês omitido)."""
    row = resolve_snapshot(db, source=source, snapshot_month=snapshot_month)
    return row.id if row is not None else None


def activate_snapshot(db: Any, *, source: str, snapshot_month: str) -> Any:
    """Ativa um snapshot COMPLETED de forma atômica. Idempotente se já ACTIVE."""
    from database.models import RegistrySnapshot

    row = db.query(RegistrySnapshot).filter(
        RegistrySnapshot.source == source,
        RegistrySnapshot.snapshot_month == snapshot_month,
    ).with_for_update().one_or_none()
    if row is None:
        raise SnapshotActivationError(
            "snapshot_not_found", f"snapshot {source}/{snapshot_month} inexistente")
    if row.status != "COMPLETED":
        raise SnapshotActivationError(
            "snapshot_not_completed",
            f"snapshot {source}/{snapshot_month} com status {row.status}: "
            "só COMPLETED pode ser ativado")
    if bool(row.is_active) and _staging_count(db, row.id) == 0:
        return row
    try:
        _apply_activation(db, row)
    except SnapshotActivationError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise SnapshotActivationError(
            "concurrent_activation",
            f"ativação concorrente de {source}/{snapshot_month}: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 — qualquer falha reverte; A segue ACTIVE
        db.rollback()
        raise SnapshotActivationError(
            "activation_failed",
            f"ativação de {source}/{snapshot_month} revertida: {exc}") from exc
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SnapshotActivationError(
            "concurrent_activation",
            f"ativação concorrente de {source}/{snapshot_month}: {exc}") from exc
    db.refresh(row)
    logger.info("registry snapshot ativado: %s/%s", source, snapshot_month)
    return row


def _staging_count(db: Any, snapshot_id: Any) -> int:
    return db.execute(sa.text(
        "SELECT count(*) FROM registry_staging_companies WHERE snapshot_id = :id"),
        {"id": str(snapshot_id)}).scalar() or 0


_CHANGED_CNPJS = """
SELECT s.cnpj FROM registry_staging_companies s
LEFT JOIN registry_companies c ON c.cnpj = s.cnpj
WHERE s.snapshot_id = :id
  AND (c.content_hash IS DISTINCT FROM s.content_hash)
"""


def _apply_activation(db: Any, snapshot: Any) -> None:
    """Aplica staging → canônico + membership + flip (dentro da transação).

    Conteúdo idêntico (mesmo `content_hash`) não reescreve o canônico nem
    os secundários — mas o membership é criado para todas as linhas
    observadas. `source_snapshot` do canônico registra a última MUDANÇA de
    conteúdo; pertencimento ao snapshot vive no membership.
    """
    snapshot_id = snapshot.id
    if _staging_count(db, snapshot_id) == 0:
        logger.warning("ativando snapshot %s/%s sem linhas em staging",
                       snapshot.source, snapshot.snapshot_month)
    # Conjunto alterado materializado antes do upsert: compara com o
    # canônico pré-ativação (linhas novas entram via LEFT JOIN). Secundários
    # só depois do upsert (FK exige a linha canônica).
    db.execute(sa.text(
        "CREATE TEMPORARY TABLE tmp_registry_changed "
        "(cnpj TEXT PRIMARY KEY) ON COMMIT DROP"))
    db.execute(sa.text(f"""
        INSERT INTO tmp_registry_changed (cnpj)
        {_CHANGED_CNPJS}
    """), {"id": str(snapshot_id)})
    cols = ", ".join(_APPLY_COLUMNS)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in _UPDATE_COLUMNS)
    db.execute(sa.text(f"""
        INSERT INTO registry_companies ({cols})
        SELECT {cols} FROM registry_staging_companies
        WHERE snapshot_id = :id
        ON CONFLICT (cnpj) DO UPDATE SET {updates}
        WHERE registry_companies.content_hash IS DISTINCT FROM EXCLUDED.content_hash
    """), {"id": str(snapshot_id)})
    db.execute(sa.text("""
        DELETE FROM registry_company_cnaes
        WHERE cnpj IN (SELECT cnpj FROM tmp_registry_changed)
    """))
    db.execute(sa.text("""
        INSERT INTO registry_company_cnaes (cnpj, cnae)
        SELECT cnpj, cnae FROM registry_staging_company_cnaes
        WHERE snapshot_id = :id
          AND cnpj IN (SELECT cnpj FROM tmp_registry_changed)
        ON CONFLICT DO NOTHING
    """), {"id": str(snapshot_id)})
    db.execute(sa.text("""
        INSERT INTO registry_snapshot_members (snapshot_id, cnpj)
        SELECT :id, cnpj FROM registry_staging_companies
        WHERE snapshot_id = :id
        ON CONFLICT DO NOTHING
    """), {"id": str(snapshot_id)})
    db.execute(sa.text("""
        UPDATE registry_snapshots SET is_active = FALSE
        WHERE source = :source AND is_active AND id != :id
    """), {"source": snapshot.source, "id": str(snapshot_id)})
    db.execute(sa.text("""
        UPDATE registry_snapshots SET is_active = TRUE WHERE id = :id
    """), {"id": str(snapshot_id)})
    db.execute(sa.text("""
        DELETE FROM registry_staging_company_cnaes WHERE snapshot_id = :id
    """), {"id": str(snapshot_id)})
    db.execute(sa.text("""
        DELETE FROM registry_staging_companies WHERE snapshot_id = :id
    """), {"id": str(snapshot_id)})
    db.flush()


def active_snapshot_id_subquery(source: str) -> Any:
    """Subquery do id ACTIVE (para joins de descoberta)."""
    from database.models import RegistrySnapshot

    return sa.select(RegistrySnapshot.id).where(
        RegistrySnapshot.source == source,
        RegistrySnapshot.is_active.is_(True),
    ).scalar_subquery()
