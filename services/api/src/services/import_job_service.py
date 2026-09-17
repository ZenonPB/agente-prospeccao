"""Serviço tenant-first do Historical Importer.

O serviço mantém o request limitado a validação/preview e deixa a mutação das
fontes canônicas para o consumer assíncrono. Nenhuma URL da origem é buscada.
"""
from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from src.db.models import (
    Campaign,
    Company,
    CompanyAlias,
    Contact,
    ContactRole,
    ContractOutcome,
    ImportAuditEvent,
    ImportJob,
    ImportJobStatus,
    ImportRowResult,
    ImportRowStatus,
    Lead,
    LeadStatus,
    LostReason,
    NegotiationStage,
    OrganizationMember,
    Person,
    PostSaleChannel,
    User,
)
from src.services.csv_import_service import clean_cnpj, normalize_import_website
from src.services.org_service import is_full_access
from services.domain_utils import normalize_domain
from src.services.historical_import_parser import (
    ImportParseError,
    ParsedSource,
    mapping_version,
    validate_mapping,
)

logger = logging.getLogger(__name__)
MAX_BATCH_SIZE = 1000
MAX_ROW_RESULTS_PAGE = 1000
MAX_RECOVERY_ATTEMPTS = 3

_ALLOWED_TRANSITIONS: dict[ImportJobStatus, frozenset[ImportJobStatus]] = {
    ImportJobStatus.DRAFT: frozenset({ImportJobStatus.PREVIEWED, ImportJobStatus.CANCELLED}),
    ImportJobStatus.PREVIEWED: frozenset({ImportJobStatus.DRAFT, ImportJobStatus.QUEUED, ImportJobStatus.CANCELLED}),
    ImportJobStatus.QUEUED: frozenset({ImportJobStatus.RUNNING, ImportJobStatus.CANCEL_REQUESTED}),
    ImportJobStatus.RUNNING: frozenset({
        ImportJobStatus.SUCCEEDED,
        ImportJobStatus.PARTIAL,
        ImportJobStatus.FAILED,
        ImportJobStatus.CANCEL_REQUESTED,
    }),
    ImportJobStatus.PARTIAL: frozenset({ImportJobStatus.QUEUED}),
    ImportJobStatus.FAILED: frozenset({ImportJobStatus.QUEUED}),
    ImportJobStatus.CANCEL_REQUESTED: frozenset({ImportJobStatus.CANCELLED}),
    ImportJobStatus.SUCCEEDED: frozenset(),
    ImportJobStatus.CANCELLED: frozenset(),
}
_TERMINAL_STATES = frozenset({ImportJobStatus.SUCCEEDED, ImportJobStatus.CANCELLED})


class ImportJobError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _status_value(status: ImportJobStatus | str | None) -> str | None:
    return status.value if isinstance(status, ImportJobStatus) else status


def _lock_query(query: Any, **kwargs: Any) -> Any:
    """Aplica lock pessimista quando a sessão é SQLAlchemy real."""
    with_for_update = getattr(query, "with_for_update", None)
    if not callable(with_for_update):
        return query
    try:
        return with_for_update(**kwargs)
    except TypeError:
        return with_for_update()


def _locked_job(db: Session, organization_id: Any, job_id: Any) -> ImportJob:
    query = db.query(ImportJob).filter(
        ImportJob.id == job_id,
        ImportJob.organization_id == organization_id,
    )
    job = _lock_query(query).first()
    if not job:
        raise ImportJobError("IMPORT_NOT_FOUND", "Importação não encontrada.", 404)
    return job


def _observed_job(db: Session, organization_id: Any, job_id: Any) -> ImportJob:
    """Lê o estado consolidado do job no início da operação, sem lock.

    A leitura é a testemunha da corrida: quem observa PREVIEWED participa da
    transição; quem observa a confirmação já persistida é um retry idempotente.
    """
    job = db.query(ImportJob).filter(
        ImportJob.id == job_id,
        ImportJob.organization_id == organization_id,
    ).first()
    if not job:
        raise ImportJobError("IMPORT_NOT_FOUND", "Importação não encontrada.", 404)
    return job


def _race_snapshot(db: Session) -> str | None:
    """Snapshot MVCC capturado na abertura da tentativa de confirmação.

    O valor é estático: ``pg_visible_in_snapshot`` avaliado contra ele responde
    de forma estável, mais tarde, se a confirmação do vencedor já estava
    consolidada quando este request começou. Retorna ``None`` em sessões sem
    PostgreSQL (provas de concorrência exigem banco real).
    """
    try:
        return db.execute(text("SELECT pg_current_snapshot()::text")).scalar()
    except (ProgrammingError, OperationalError, NotImplementedError):
        return None


def _confirmation_visible(db: Session, confirm_xid: Any, snapshot: str | None) -> bool:
    """A confirmação do vencedor já estava consolidada no snapshot de abertura?

    ``True`` significa que este request começou depois da confirmação — é o
    retry idempotente. ``False`` significa que ele disputou a corrida (a
    confirmação ainda não era visível quando ele abriu): perdedor, nunca vira
    sucesso. Sem testemunha (sessão não-PostgreSQL) não reconhece replay.
    """
    if not confirm_xid or not snapshot:
        return False
    return bool(
        db.execute(
            text(
                "SELECT pg_visible_in_snapshot("
                "CAST(:xid AS xid8), CAST(:snapshot AS pg_snapshot))"
            ),
            {"xid": str(confirm_xid), "snapshot": snapshot},
        ).scalar()
    )


def confirmation_replay_state(
    job: ImportJob,
    *,
    idempotency_key: str,
    confirmed_mapping_version: str,
    expected_version: int,
) -> str | None:
    """Classifica um job já confirmado contra o contrato do request atual.

    - ``None``: o job ainda não carrega uma confirmação persistida.
    - ``"replay"``: retry idempotente da confirmação vencedora — mesma chave,
      mesmo snapshot de mapping e mesma versão-base, então a operação já
      concluída é devolvida sem nova transição.
    - ``"version_conflict"``: mesma chave/mapping, mas a versão-base diverge —
      típico de concorrente perdedor da corrida original ou de payload
      divergente; nunca vira sucesso.
    - ``"idempotency_conflict"``: a chave já foi usada com outro contrato.
    """
    if job.idempotency_key is None:
        return None
    if job.idempotency_key != idempotency_key:
        # A confirmação persistida pertence a outro contrato: se o request já
        # ficou para trás no lifecycle é conflito de versão; se trouxe a versão
        # corrente, a chave é incompatível com o estado consolidado.
        if job.expected_version != expected_version:
            return "version_conflict"
        return "idempotency_conflict"
    if job.mapping_version != confirmed_mapping_version:
        return "idempotency_conflict"
    if getattr(job, "confirm_base_version", None) != expected_version:
        return "version_conflict"
    return "replay"


def _assert_actor_authorized(job: ImportJob, actor_id: Any, member: Any = None) -> None:
    """Impede mutações sem ator e limita CONSULTOR à própria importação."""
    if actor_id is None:
        raise ImportJobError("ACTOR_REQUIRED", "A ação exige um ator autenticado.", 403)
    if member is not None:
        if str(getattr(member, "organization_id", "")) != str(job.organization_id):
            raise ImportJobError("UNAUTHORIZED", "A autorização não foi concedida.", 403)
        if str(getattr(member, "user_id", "")) != str(actor_id):
            raise ImportJobError("UNAUTHORIZED", "A autorização não foi concedida.", 403)
        if not is_full_access(member) and str(job.actor_id) != str(actor_id):
            raise ImportJobError("UNAUTHORIZED", "A autorização não foi concedida.", 403)
        return
    if job.actor_id is None or str(job.actor_id) != str(actor_id):
        raise ImportJobError("UNAUTHORIZED", "A autorização não foi concedida.", 403)


def _assert_expected_version(job: ImportJob, expected_version: int | None) -> None:
    if expected_version is None:
        raise ImportJobError("VERSION_REQUIRED", "A versão esperada é obrigatória.", 422)
    if job.expected_version != expected_version:
        raise ImportJobError("VERSION_CONFLICT", "A versão da importação está desatualizada.", 409)


def _claim_confirmation(
    db: Session,
    job: ImportJob,
    *,
    actor_id: Any,
    expected_version: int,
    idempotency_key: str,
    mapping: dict[str, str | None],
    mapping_version_value: str,
) -> ImportJob:
    """Reserva a confirmação com compare-and-swap atômico no PostgreSQL.

    Um único ``UPDATE`` condicional em ``(id, organization_id,
    expected_version, status, idempotency_key IS NULL)`` decide a corrida no
    banco: quem casa a linha vence e avança a versão exatamente uma vez; os
    demais recebem ``rowcount`` 0 e respondem ``VERSION_CONFLICT``. Como só o
    vencedor segue para auditoria/commit, nenhum efeito é duplicado e o
    resultado não depende de escalonamento entre workers ou processos.
    """
    from sqlalchemy import update

    result = db.execute(
        update(ImportJob)
        .where(
            ImportJob.id == job.id,
            ImportJob.organization_id == job.organization_id,
            ImportJob.expected_version == expected_version,
            ImportJob.status == ImportJobStatus.PREVIEWED,
            ImportJob.idempotency_key.is_(None),
        )
        .values(
            status=ImportJobStatus.QUEUED,
            expected_version=ImportJob.expected_version + 1,
            idempotency_key=idempotency_key,
            mapping=mapping,
            mapping_version=mapping_version_value,
            confirm_base_version=expected_version,
            confirm_xid=text("pg_current_xact_id()::text"),
            error_code=None,
            error_message=None,
        )
    )
    if result.rowcount != 1:
        # Outro participante da corrida efetivou a transição (ou o estado já
        # não é confirmável): este request perdeu e não pode virar sucesso.
        raise ImportJobError("VERSION_CONFLICT", "A versão da importação está desatualizada.", 409)
    # A linha está reservada por esta transação: os valores abaixo são
    # exatamente os persistidos pelo CAS vencedor.
    job.status = ImportJobStatus.QUEUED
    job.expected_version = expected_version + 1
    job.idempotency_key = idempotency_key
    job.mapping = mapping
    job.mapping_version = mapping_version_value
    job.confirm_base_version = expected_version
    job.confirm_xid = db.execute(
        text("SELECT pg_current_xact_id()::text")
    ).scalar()
    job.error_code = None
    job.error_message = None
    _audit(
        db, job, "STATUS_CHANGED", actor_id,
        ImportJobStatus.PREVIEWED, ImportJobStatus.QUEUED,
        {"mapping_version": mapping_version_value},
    )
    return job


def _transition(
    db: Session,
    job: ImportJob,
    target: ImportJobStatus,
    *,
    actor_id: Any,
    expected_version: int | None,
    member: Any = None,
    allow_system: bool = False,
    detail: dict[str, Any] | None = None,
) -> ImportJob:
    """Executa uma transição única, versionada e auditada."""
    if job.organization_id is None:
        raise ImportJobError("ORGANIZATION_REQUIRED", "Importação sem workspace não pode ser processada.", 409)
    if not allow_system:
        _assert_actor_authorized(job, actor_id, member)
    if expected_version is not None and job.expected_version != expected_version:
        raise ImportJobError("VERSION_CONFLICT", "A versão da importação está desatualizada.", 409)
    current = job.status
    if current in _TERMINAL_STATES:
        raise ImportJobError("STATE_TERMINAL", "A importação está em estado terminal.", 409)
    if target not in _ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise ImportJobError(
            "INVALID_TRANSITION",
            f"Transição inválida: {_status_value(current)} → {_status_value(target)}.",
            409,
        )
    job.status = target
    job.expected_version += 1
    audit_detail = dict(detail or {})
    if allow_system:
        audit_detail.setdefault("actor_type", "system")
    _audit(db, job, "STATUS_CHANGED", actor_id, current, target, audit_detail)
    return job


def _audit(
    db: Session,
    job: ImportJob,
    action: str,
    actor_id: Any = None,
    from_status: ImportJobStatus | str | None = None,
    to_status: ImportJobStatus | str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    db.add(
        ImportAuditEvent(
            import_job_id=job.id,
            organization_id=job.organization_id,
            actor_id=actor_id,
            action=action,
            from_status=_status_value(from_status),
            to_status=_status_value(to_status),
            detail=detail or {},
            correlation_id=job.correlation_id,
        )
    )


def _campaign(db: Session, organization_id: Any, campaign_id: Any) -> Campaign | None:
    if campaign_id is None:
        return None
    return db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.organization_id == organization_id,
    ).first()


def serialize_job(job: ImportJob, include_preview: bool = True) -> dict[str, Any]:
    payload = {
        "id": str(job.id),
        "organization_id": str(job.organization_id),
        "campaign_id": str(job.campaign_id) if job.campaign_id else None,
        "status": _status_value(job.status),
        "source_hash": job.source_hash,
        "source_filename": job.source_filename,
        "source_format": job.source_format,
        "mapping_version": job.mapping_version,
        "expected_version": job.expected_version,
        "total_rows": job.total_rows,
        "accepted_rows": job.accepted_rows,
        "duplicate_rows": job.duplicate_rows,
        "rejected_rows": job.rejected_rows,
        "failed_rows": job.failed_rows,
        "unprocessed_rows": job.unprocessed_rows,
        "attempts": job.attempts,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
    if include_preview:
        payload.update({
            "headers": list(job.source_headers or []),
            "preview_rows": list(job.preview_rows or []),
            "suggested_mapping": job.mapping or {},
            "dry_run_report": job.dry_run_report,
        })
    return payload


def _validated_mapping(job: ImportJob, mapping: dict[str, str | None]) -> tuple[dict[str, str | None], str]:
    try:
        valid = validate_mapping(list(job.source_headers), mapping)
    except ImportParseError as exc:
        raise ImportJobError(exc.code, exc.message, 422) from exc
    return valid, mapping_version(list(job.source_headers), valid)


def _mapping_for_job(job: ImportJob, mapping: dict[str, str | None], expected_version: int) -> tuple[dict[str, str | None], str]:
    _assert_expected_version(job, expected_version)
    return _validated_mapping(job, mapping)


def create_preview(
    db: Session,
    organization_id: Any,
    actor_id: Any,
    content: bytes,
    filename: str | None,
    content_type: str | None,
    campaign_id: Any = None,
    idempotency_key: str | None = None,
    correlation_id: str | None = None,
    member: Any = None,
) -> ImportJob:
    if organization_id is None:
        raise ImportJobError("ORGANIZATION_REQUIRED", "A importação exige um workspace válido.", 403)
    if actor_id is None:
        raise ImportJobError("ACTOR_REQUIRED", "A importação exige um ator autenticado.", 403)
    try:
        parsed: ParsedSource = __import__(
            "src.services.historical_import_parser", fromlist=["parse_source"]
        ).parse_source(content, filename, content_type)
    except ImportParseError as exc:
        raise ImportJobError(exc.code, exc.message, 422) from exc

    campaign = _campaign(db, organization_id, campaign_id)
    if campaign_id is not None and campaign is None:
        raise ImportJobError("CAMPAIGN_NOT_FOUND", "Campanha não encontrada.", 404)
    if idempotency_key:
        existing = db.query(ImportJob).filter(
            ImportJob.organization_id == organization_id,
            ImportJob.idempotency_key == idempotency_key,
        ).first()
        if existing:
            _assert_actor_authorized(existing, actor_id, member)
            if existing.source_hash != parsed.source_hash:
                raise ImportJobError("IDEMPOTENCY_CONFLICT", "A chave já foi usada por outro arquivo.", 409)
            return existing

    job = ImportJob(
        organization_id=organization_id,
        campaign_id=campaign.id if campaign else None,
        actor_id=actor_id,
        source_hash=parsed.source_hash,
        idempotency_key=None,
        source_filename=(filename or "origem").split("\\")[-1].split("/")[-1][:255],
        source_format=parsed.source_format,
        source_headers=parsed.headers,
        source_rows=parsed.rows,
        preview_rows=parsed.preview_rows,
        mapping=parsed.suggested_mapping,
        mapping_version=parsed.mapping_version,
        status=ImportJobStatus.DRAFT,
        expected_version=1,
        total_rows=len(parsed.rows),
        unprocessed_rows=len(parsed.rows),
        correlation_id=correlation_id,
    )
    db.add(job)
    db.flush()
    _audit(db, job, "PREVIEW_CREATED", actor_id, None, ImportJobStatus.DRAFT, {
        "source_format": parsed.source_format,
        "total_rows": len(parsed.rows),
        "source_hash_prefix": parsed.source_hash[:12],
    })
    _transition(
        db,
        job,
        ImportJobStatus.PREVIEWED,
        actor_id=actor_id,
        expected_version=job.expected_version,
        member=member,
        detail={"preview_created": True},
    )
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, organization_id: Any, job_id: Any) -> ImportJob:
    job = db.query(ImportJob).filter(
        ImportJob.id == job_id,
        ImportJob.organization_id == organization_id,
    ).first()
    if not job:
        raise ImportJobError("IMPORT_NOT_FOUND", "Importação não encontrada.", 404)
    return job


def list_rows(
    db: Session,
    organization_id: Any,
    job_id: Any,
    status: str | None = None,
    offset: int = 0,
    limit: int = 1000,
) -> dict[str, Any]:
    job = get_job(db, organization_id, job_id)
    limit = min(max(limit, 1), MAX_ROW_RESULTS_PAGE)
    query = db.query(ImportRowResult).filter(
        ImportRowResult.import_job_id == job.id,
        ImportRowResult.organization_id == organization_id,
    )
    if status:
        if status not in {item.value for item in ImportRowStatus}:
            raise ImportJobError("ROW_STATUS_INVALID", "Status de linha inválido.", 422)
        query = query.filter(ImportRowResult.status == status)
    rows = query.order_by(ImportRowResult.line_number.asc()).offset(max(offset, 0)).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "import_id": str(job.id),
        "offset": max(offset, 0),
        "limit": limit,
        "has_more": has_more,
        "rows": [
            {
                "line_number": row.line_number,
                "status": _status_value(row.status),
                "reason_code": row.reason_code,
                "message": row.message,
                "lead_id": str(row.lead_id) if row.lead_id else None,
                "company_id": str(row.company_id) if row.company_id else None,
                "person_id": str(row.person_id) if row.person_id else None,
                "identity_decision": row.identity_decision,
                "provenance": row.provenance,
            }
            for row in rows
        ],
    }


def dry_run(
    db: Session,
    organization_id: Any,
    actor_id: Any,
    job_id: Any,
    mapping: dict[str, str | None],
    expected_version: int,
    member: Any = None,
) -> dict[str, Any]:
    job = _locked_job(db, organization_id, job_id)
    _assert_actor_authorized(job, actor_id, member)
    _assert_expected_version(job, expected_version)
    if job.status != ImportJobStatus.PREVIEWED:
        raise ImportJobError("STATE_INVALID", "Dry-run exige uma importação em PREVIEWED.", 409)
    valid_mapping, version = _mapping_for_job(job, mapping, expected_version)
    report = _dry_run_report(db, job, valid_mapping)
    job.mapping = valid_mapping
    job.mapping_version = version
    job.dry_run_report = report
    job.expected_version += 1
    _audit(db, job, "DRY_RUN_COMPLETED", actor_id, job.status, job.status, {
        "mapping_version": version,
        "accepted": report["accepted"],
        "duplicate": report["duplicate"],
        "rejected": report["rejected"],
    })
    db.commit()
    db.refresh(job)
    return {"job": serialize_job(job), "report": report}


def confirm(
    db: Session,
    organization_id: Any,
    actor_id: Any,
    job_id: Any,
    mapping: dict[str, str | None],
    mapping_version_value: str,
    expected_version: int,
    idempotency_key: str,
    member: Any = None,
) -> ImportJob:
    """Confirma a importação com corrida decidida atomicamente pelo banco.

    O fluxo separa duas situações distintas que compartilham o mesmo payload:

    - **participante da corrida** — observa o job em ``PREVIEWED`` e tenta o
      compare-and-swap; exatamente um vence e os demais recebem
      ``VERSION_CONFLICT``;
    - **retry idempotente** — observa a confirmação já persistida com a mesma
      chave, mapping e versão-base e recebe o mesmo job, sem nova transição.

    Dois gates separam os casos. O primeiro compara o contrato persistido
    (chave, mapping, ``confirm_base_version``). O segundo é a testemunha MVCC:
    o replay só é aceito quando a confirmação do vencedor já estava visível no
    snapshot capturado na abertura deste request. Um perdedor da corrida
    original carrega o mesmo contrato, mas sua abertura antecede o commit do
    vencedor — logo recebe ``VERSION_CONFLICT``, independente do escalonamento
    ou da quantidade de workers.
    """
    if not idempotency_key or len(idempotency_key) > 255:
        raise ImportJobError("IDEMPOTENCY_REQUIRED", "idempotency_key é obrigatório.", 422)

    # Primeira instrução da tentativa: fixa a testemunha da corrida antes de
    # qualquer leitura ou write, para a classificação ser estável daqui em diante.
    snapshot = _race_snapshot(db)
    job = _observed_job(db, organization_id, job_id)
    _assert_actor_authorized(job, actor_id, member)
    valid_mapping, computed_version = _validated_mapping(job, mapping)
    if mapping_version_value != computed_version:
        raise ImportJobError("MAPPING_VERSION_CONFLICT", "O mapping mudou; execute um novo dry-run.", 409)

    replay = confirmation_replay_state(
        job,
        idempotency_key=idempotency_key,
        confirmed_mapping_version=computed_version,
        expected_version=expected_version,
    )
    if replay is not None:
        if replay == "replay" and not _confirmation_visible(db, job.confirm_xid, snapshot):
            # Mesmo contrato persistido, mas a confirmação ainda não era
            # visível quando este request abriu: perdedor da corrida original.
            replay = "version_conflict"
        if replay == "replay":
            return job
        if replay == "version_conflict":
            raise ImportJobError("VERSION_CONFLICT", "A versão da importação está desatualizada.", 409)
        if replay == "idempotency_conflict":
            raise ImportJobError("IDEMPOTENCY_CONFLICT", "A importação já foi confirmada com outro contrato.", 409)

    existing = db.query(ImportJob).filter(
        ImportJob.organization_id == organization_id,
        ImportJob.idempotency_key == idempotency_key,
    ).first()
    if existing:
        _assert_actor_authorized(existing, actor_id, member)
        if existing.source_hash != job.source_hash:
            raise ImportJobError("IDEMPOTENCY_CONFLICT", "A chave já foi usada por outro arquivo.", 409)
        if existing.mapping_version != computed_version:
            raise ImportJobError("IDEMPOTENCY_CONFLICT", "A chave já foi usada com outro mapping.", 409)
        if (
            getattr(existing, "confirm_base_version", None) == expected_version
            and _confirmation_visible(db, existing.confirm_xid, snapshot)
        ):
            return existing
        raise ImportJobError("VERSION_CONFLICT", "A versão da importação está desatualizada.", 409)

    _assert_expected_version(job, expected_version)
    if job.status != ImportJobStatus.PREVIEWED or not job.dry_run_report:
        raise ImportJobError("DRY_RUN_REQUIRED", "Execute o dry-run antes de confirmar.", 409)
    if computed_version != job.mapping_version:
        raise ImportJobError("MAPPING_VERSION_CONFLICT", "O mapping mudou; execute um novo dry-run.", 409)

    _claim_confirmation(
        db,
        job,
        actor_id=actor_id,
        expected_version=expected_version,
        idempotency_key=idempotency_key,
        mapping=valid_mapping,
        mapping_version_value=mapping_version_value,
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.query(ImportJob).filter(
            ImportJob.organization_id == organization_id,
            ImportJob.idempotency_key == idempotency_key,
        ).first()
        if (
            existing
            and existing.source_hash == job.source_hash
            and existing.mapping_version == computed_version
            and getattr(existing, "confirm_base_version", None) == expected_version
            and _confirmation_visible(db, existing.confirm_xid, snapshot)
        ):
            _assert_actor_authorized(existing, actor_id, member)
            return existing
        raise ImportJobError("IDEMPOTENCY_CONFLICT", "Não foi possível confirmar a importação concorrente.", 409) from exc
    db.refresh(job)
    return job


def cancel(
    db: Session,
    organization_id: Any,
    actor_id: Any,
    job_id: Any,
    expected_version: int | None = None,
    member: Any = None,
) -> ImportJob:
    job = _locked_job(db, organization_id, job_id)
    _assert_actor_authorized(job, actor_id, member)
    _assert_expected_version(job, expected_version)
    if job.status in _TERMINAL_STATES:
        raise ImportJobError("STATE_TERMINAL", "A importação está em estado terminal.", 409)
    if job.status == ImportJobStatus.CANCEL_REQUESTED:
        if expected_version is not None and job.expected_version != expected_version:
            raise ImportJobError("VERSION_CONFLICT", "A versão da importação está desatualizada.", 409)
        return job
    target = (
        ImportJobStatus.CANCELLED
        if job.status in (ImportJobStatus.DRAFT, ImportJobStatus.PREVIEWED)
        else ImportJobStatus.CANCEL_REQUESTED
    )
    _transition(
        db,
        job,
        target,
        actor_id=actor_id,
        expected_version=expected_version,
        member=member,
        detail={"cancel_requested": target == ImportJobStatus.CANCEL_REQUESTED},
    )
    if target == ImportJobStatus.CANCELLED:
        job.completed_at = _now()
    db.commit()
    db.refresh(job)
    return job


def recover(
    db: Session,
    organization_id: Any,
    actor_id: Any,
    job_id: Any,
    expected_version: int,
    member: Any = None,
) -> ImportJob:
    job = _locked_job(db, organization_id, job_id)
    _assert_actor_authorized(job, actor_id, member)
    _assert_expected_version(job, expected_version)
    if job.status not in (ImportJobStatus.FAILED, ImportJobStatus.PARTIAL):
        raise ImportJobError("STATE_INVALID", "Recovery exige uma importação FAILED ou PARTIAL.", 409)
    if job.attempts >= MAX_RECOVERY_ATTEMPTS:
        raise ImportJobError("RETRY_LIMIT", "O limite de três tentativas foi atingido.", 409)
    db.query(ImportRowResult).filter(
        ImportRowResult.import_job_id == job.id,
        ImportRowResult.organization_id == organization_id,
        ImportRowResult.status == ImportRowStatus.FAILED,
    ).delete(synchronize_session=False)
    job.failed_rows = 0
    job.error_code = None
    job.error_message = None
    _transition(
        db,
        job,
        ImportJobStatus.QUEUED,
        actor_id=actor_id,
        expected_version=expected_version,
        member=member,
        detail={"recovery": True, "retry_attempt": job.attempts + 1},
    )
    db.commit()
    db.refresh(job)
    return job


def _normalize_token(value: str) -> str:
    raw = unicodedata.normalize("NFKD", value.strip().upper())
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z0-9]+", "_", raw).strip("_")


def _parse_datetime_field(value: str, field: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    candidate = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        parsed = None
        for fmt in ("%d/%m/%Y", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
            try:
                parsed = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            raise ValueError(f"{field} deve ser data ISO ou DD/MM/AAAA")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_decimal_field(value: str, field: str) -> Decimal | None:
    value = value.strip()
    if not value:
        return None
    compact = re.sub(r"[^0-9,.-]", "", value)
    if "," in compact and "." in compact and compact.rfind(",") > compact.rfind("."):
        compact = compact.replace(".", "").replace(",", ".")
    elif "," in compact:
        compact = compact.replace(",", ".")
    try:
        parsed = Decimal(compact)
    except InvalidOperation as exc:
        raise ValueError(f"{field} inválido") from exc
    if parsed < 0:
        raise ValueError(f"{field} não pode ser negativo")
    return parsed


def _parse_enum_field(value: str, enum_cls: type, field: str):
    value = value.strip()
    if not value:
        return None
    token = _normalize_token(value)
    aliases = {
        "REUNIAO_MARCADA": "REUNIAO_MARCADA",
        "REUNIAO_FEITA": "REUNIAO_FEITA",
        "PROPOSTA_ENVIADA": "PROPOSTA_ENVIADA",
        "ORCAMENTO": "ORCAMENTO",
        "EM_ANALISE": "EM_ANALISE",
        "NAO_RESPONDEU": "NAO_RESPONDEU",
        "PRECO": "PRECO",
        "WHATSAPP": "WHATSAPP",
        "E_MAIL": "EMAIL",
        "EMAIL": "EMAIL",
    }
    token = aliases.get(token, token)
    for item in enum_cls:
        if token in {_normalize_token(item.name), _normalize_token(str(item.value))}:
            return item
    allowed = ", ".join(str(item.value) for item in enum_cls)
    raise ValueError(f"{field} inválido; use: {allowed}")


def _normalized_row(job: ImportJob, row: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    mapping = job.mapping or {}
    for index, header in enumerate(job.source_headers or []):
        target = mapping.get(header)
        if target:
            result[target] = (row[index] if index < len(row) else "").strip()
    result["website"] = normalize_import_website(result.get("website")) or ""
    result["cnpj"] = clean_cnpj(result.get("cnpj")) or ""
    result["email"] = result.get("email", "").strip().lower()
    result["owner_email"] = result.get("owner_email", "").strip().lower()
    return result


def _lead_duplicate(db: Session, organization_id: Any, data: dict[str, str], place_id: str) -> Lead | None:
    conditions = [Lead.place_id == place_id]
    if data.get("cnpj"):
        conditions.append(Lead.cnpj == data["cnpj"])
    if data.get("website"):
        conditions.append(Lead.website == data["website"])
    if data.get("normalized_domain"):
        conditions.append(Lead.normalized_domain == data["normalized_domain"])
    return db.query(Lead).filter(
        Lead.organization_id == organization_id,
        or_(*conditions),
    ).first()


def _company_decision(db: Session, organization_id: Any, data: dict[str, str]) -> tuple[str, Company | None, dict[str, Any]]:
    matches: dict[str, list[Company]] = {}
    if data.get("cnpj"):
        matches["cnpj"] = db.query(Company).filter(
            Company.organization_id == organization_id, Company.cnpj == data["cnpj"]
        ).all()
    if data.get("normalized_domain"):
        matches["domain"] = db.query(Company).filter(
            Company.organization_id == organization_id, Company.normalized_domain == data["normalized_domain"]
        ).all()
    # O place_id sintético serve para idempotência do histórico, não é tratado
    # como identificador externo forte para merge de Company.
    alias_values = [value for value in (data.get("normalized_domain"),) if value]
    if alias_values:
        aliases = db.query(CompanyAlias).filter(
            CompanyAlias.organization_id == organization_id,
            CompanyAlias.alias_value.in_(alias_values),
        ).all()
        if aliases:
            matches["alias"] = db.query(Company).filter(
                Company.organization_id == organization_id,
                Company.id.in_([alias.company_id for alias in aliases]),
            ).all()
    unique = {str(company.id): company for values in matches.values() for company in values}
    if len(unique) > 1:
        return "REVIEW", None, {"classification": "HYPOTHESIS", "reason": "CONFLICTING_IDENTIFIERS", "candidates": list(unique)}
    if any(len(values) > 1 for values in matches.values()):
        return "REVIEW", None, {"classification": "HYPOTHESIS", "reason": "AMBIGUOUS_IDENTIFIER", "candidates": list(unique)}
    if unique:
        kind = next(kind for kind, values in matches.items() if values)
        return "CONFIRMED", next(iter(unique.values())), {"classification": "FACT", "match_kind": kind, "strong_identifier": True}

    name = data.get("name", "").strip()
    if name:
        candidates = db.query(Company).filter(
            Company.organization_id == organization_id,
            or_(Company.company_name == name, Company.name == name),
        ).all()
        if candidates:
            return "REVIEW", None, {"classification": "HYPOTHESIS", "reason": "NAME_ONLY_MATCH", "candidates": [str(item.id) for item in candidates]}
    if not data.get("cnpj") and not data.get("normalized_domain"):
        return "NEW", None, {
            "classification": "FACT",
            "reason": "HISTORICAL_NEW_ENTITY",
            "strong_identifier": False,
            "note": "A fonte histórica afirma a existência; nenhum merge por nome é feito.",
        }
    return "NOT_FOUND", None, {"classification": "FACT", "reason": "IDENTIFIER_NOT_FOUND", "strong_identifier": True}


def _person_decision(db: Session, organization_id: Any, company_id: Any, data: dict[str, str]) -> tuple[str, Person | None, dict[str, Any]]:
    name = data.get("contact_name", "").strip()
    if not name and not data.get("email") and not data.get("phone"):
        return "UNKNOWN", None, {"classification": "UNKNOWN", "reason": "NO_PERSON_SIGNAL"}
    query = db.query(Person).filter(Person.organization_id == organization_id)
    if company_id:
        query = query.filter(Person.company_id == company_id)
    matches: dict[str, list[Person]] = {}
    if data.get("email"):
        matches["email"] = query.filter(Person.email == data["email"]).all()
    if data.get("phone"):
        matches["phone"] = query.filter(Person.phone == data["phone"]).all()
    unique = {str(person.id): person for values in matches.values() for person in values}
    if len(unique) > 1 or any(len(values) > 1 for values in matches.values()):
        return "REVIEW", None, {"classification": "HYPOTHESIS", "reason": "AMBIGUOUS_PERSON", "candidates": list(unique)}
    if unique:
        kind = next(kind for kind, values in matches.items() if values)
        return "CONFIRMED", next(iter(unique.values())), {"classification": "FACT", "match_kind": kind}
    if name:
        name_candidates = query.filter(Person.name == name).all()
        if name_candidates:
            return "REVIEW", None, {"classification": "HYPOTHESIS", "reason": "NAME_ONLY_MATCH", "candidates": [str(item.id) for item in name_candidates]}
    return "NOT_FOUND", None, {"classification": "FACT", "reason": "PERSON_IDENTIFIER_NOT_FOUND"}


def _commercial_decision(db: Session, job: ImportJob, data: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        status = _parse_enum_field(data.get("status", ""), LeadStatus, "status") or LeadStatus.NOVO
        lost_reason = _parse_enum_field(data.get("lost_reason", ""), LostReason, "lost_reason")
        if status == LeadStatus.PERDIDO and lost_reason is None:
            return None, "PERDIDO exige lost_reason."
        if status != LeadStatus.PERDIDO and lost_reason is not None:
            return None, "lost_reason só pode ser usado com status PERDIDO."
        negotiation_stage = _parse_enum_field(data.get("negotiation_stage", ""), NegotiationStage, "negotiation_stage")
        contract_outcome = _parse_enum_field(data.get("contract_outcome", ""), ContractOutcome, "contract_outcome")
        post_sale_channel = _parse_enum_field(data.get("post_sale_channel", ""), PostSaleChannel, "post_sale_channel")
        value = _parse_decimal_field(data.get("value", ""), "value")
        fields = {
            "status": status,
            "lost_reason": lost_reason,
            "negotiation_stage": negotiation_stage,
            "contract_outcome": contract_outcome,
            "post_sale_channel": post_sale_channel,
            "value": value,
            "assigned_at": _parse_datetime_field(data.get("assigned_at", ""), "assigned_at"),
            "next_action_at": _parse_datetime_field(data.get("next_action_at", ""), "next_action_at"),
            "last_contacted_at": _parse_datetime_field(data.get("last_contacted_at", ""), "last_contacted_at"),
            "outcome_date": _parse_datetime_field(data.get("outcome_date", ""), "outcome_date"),
            "post_sale_contacted_at": _parse_datetime_field(data.get("post_sale_contacted_at", ""), "post_sale_contacted_at"),
            "expected_close_date": _parse_datetime_field(data.get("expected_close_date", ""), "expected_close_date"),
            "notes": data.get("notes", "").strip() or None,
            "owner_user_id": None,
        }
    except ValueError as exc:
        return None, str(exc)

    owner_email = data.get("owner_email", "").strip().lower()
    if owner_email:
        owner = (
            db.query(User)
            .join(OrganizationMember, OrganizationMember.user_id == User.id)
            .filter(
                OrganizationMember.organization_id == job.organization_id,
                User.email == owner_email,
            )
            .first()
        )
        if owner is None:
            return None, "owner_email não pertence ao workspace."
        fields["owner_user_id"] = owner.id
    return fields, None


def _inspect_row(db: Session, job: ImportJob, row: list[str]) -> dict[str, Any]:
    data = _normalized_row(job, row)
    if not data.get("name"):
        return {"status": ImportRowStatus.REJECTED, "reason_code": "NAME_REQUIRED", "message": "Nome da empresa ausente."}
    campaign = _campaign(db, job.organization_id, job.campaign_id)
    data["city"] = data.get("city") or (campaign.target_city if campaign else "")
    data["state"] = data.get("state") or (campaign.target_state if campaign else "")
    data["category"] = data.get("category") or (campaign.target_segment if campaign else "")
    data["normalized_domain"] = normalize_domain(data.get("website")) or ""
    place_id = "historical_" + hashlib.sha256(
        f"{data.get('name','').lower()}|{data.get('city','').lower()}|{data.get('website','').lower()}|{data.get('cnpj','')}".encode()
    ).hexdigest()[:24]
    duplicate = _lead_duplicate(db, job.organization_id, data, place_id)
    if duplicate:
        return {"status": ImportRowStatus.DUPLICATE, "reason_code": "LEAD_ALREADY_EXISTS", "message": "Lead já reconhecido no workspace.", "lead": duplicate, "data": data, "place_id": place_id}
    company_kind, company, company_decision = _company_decision(db, job.organization_id, data)
    if company_kind == "REVIEW":
        return {"status": ImportRowStatus.REJECTED, "reason_code": "COMPANY_REVIEW_REQUIRED", "message": "Identidade da empresa requer revisão.", "identity_decision": {"company": company_decision}, "data": data, "place_id": place_id}
    person_kind, person, person_decision = _person_decision(db, job.organization_id, company.id if company else None, data)
    if person_kind == "REVIEW":
        return {"status": ImportRowStatus.REJECTED, "reason_code": "PERSON_REVIEW_REQUIRED", "message": "Identidade da pessoa requer revisão.", "identity_decision": {"company": company_decision, "person": person_decision}, "data": data, "place_id": place_id}
    commercial, commercial_error = _commercial_decision(db, job, data)
    if commercial_error:
        return {
            "status": ImportRowStatus.REJECTED,
            "reason_code": "COMMERCIAL_DATA_INVALID",
            "message": commercial_error,
            "identity_decision": {"company": company_decision, "person": person_decision},
            "data": data,
            "place_id": place_id,
        }
    return {
        "status": ImportRowStatus.ACCEPTED,
        "reason_code": None,
        "message": None,
        "data": data,
        "place_id": place_id,
        "company": company,
        "company_decision": company_decision,
        "person": person,
        "person_decision": person_decision,
        "commercial": commercial,
        "identity_decision": {"company": company_decision, "person": person_decision},
    }


def _dry_run_report(db: Session, job: ImportJob, mapping: dict[str, str | None]) -> dict[str, Any]:
    previous = job.mapping
    job.mapping = mapping
    counts = {"accepted": 0, "duplicate": 0, "rejected": 0, "failed": 0}
    errors: list[dict[str, Any]] = []
    try:
        for line_number, row in enumerate(job.source_rows or [], start=2):
            result = _inspect_row(db, job, row)
            key = result["status"].value.lower()
            counts[key] += 1
            if result["status"] in (ImportRowStatus.REJECTED, ImportRowStatus.FAILED) and len(errors) < 100:
                errors.append({"line_number": line_number, "status": result["status"].value, "reason_code": result.get("reason_code"), "message": result.get("message")})
    finally:
        job.mapping = previous
    return {**counts, "total_rows": len(job.source_rows or []), "errors": errors}


def _create_canonical_row(db: Session, job: ImportJob, inspected: dict[str, Any], line_number: int) -> dict[str, Any]:
    if inspected["status"] != ImportRowStatus.ACCEPTED:
        return inspected
    data = inspected["data"]
    commercial = inspected.get("commercial") or {}
    company = inspected.get("company")
    if company is None:
        company = Company(
            organization_id=job.organization_id,
            company_name=data["name"],
            name=data["name"],
            cnpj=data.get("cnpj") or None,
            website=data.get("website") or None,
            normalized_domain=data.get("normalized_domain") or None,
            phone=data.get("phone") or None,
            address=data.get("address") or None,
            city=data.get("city") or None,
            state=data.get("state") or None,
            country="Brasil",
            category=data.get("category") or None,
        )
        db.add(company)
        db.flush()
    from services.company_person_service import CompanyPersonService
    CompanyPersonService.register_company_aliases(
        db, job.organization_id, company.id,
        {"place_id": inspected["place_id"], "normalized_domain": data.get("normalized_domain"), "provider": "historical_import"},
    )
    lead = Lead(
        organization_id=job.organization_id,
        campaign_id=job.campaign_id,
        company_id=company.id,
        place_id=inspected["place_id"],
        name=data["name"],
        company_name=data["name"],
        cnpj=data.get("cnpj") or None,
        website=data.get("website") or None,
        normalized_domain=data.get("normalized_domain") or None,
        phone=data.get("phone") or None,
        whatsapp=data.get("whatsapp") or data.get("phone") or None,
        email=data.get("email") or None,
        city=data.get("city") or None,
        state=data.get("state") or None,
        address=data.get("address") or None,
        category=data.get("category") or None,
        instagram_url=data.get("instagram") or None,
        status=commercial.get("status") or LeadStatus.NOVO,
        lost_reason=commercial.get("lost_reason"),
        negotiation_stage=commercial.get("negotiation_stage"),
        contract_outcome=commercial.get("contract_outcome"),
        post_sale_channel=commercial.get("post_sale_channel"),
        value=commercial.get("value"),
        assigned_to_id=commercial.get("owner_user_id"),
        assigned_at=commercial.get("assigned_at"),
        next_action_at=commercial.get("next_action_at"),
        last_contacted_at=commercial.get("last_contacted_at"),
        outcome_date=commercial.get("outcome_date"),
        post_sale_contacted_at=commercial.get("post_sale_contacted_at"),
        expected_close_date=commercial.get("expected_close_date"),
        notes=commercial.get("notes"),
        discovery_provenance={
            "source": "historical_import",
            "import_job_id": str(job.id),
            "source_hash": job.source_hash,
            "line_number": line_number,
            "classification": "FACT",
            "observed_at": _now().isoformat(),
            "historical_fields": sorted(key for key in data if key in {
                "status", "owner_email", "assigned_at", "notes", "next_action_at",
                "last_contacted_at", "negotiation_stage", "contract_outcome",
                "outcome_date", "post_sale_contacted_at", "post_sale_channel",
                "value", "expected_close_date", "lost_reason",
            } and data.get(key)),
        },
    )
    db.add(lead)
    db.flush()
    person = inspected.get("person")
    contact_name = data.get("contact_name")
    if person is None and contact_name:
        person = CompanyPersonService.get_or_create_person(
            db, job.organization_id, company.id,
            {
                "name": contact_name,
                "email": data.get("email") or None,
                "phone": data.get("phone") or data.get("whatsapp") or None,
                "role": ContactRole.OUTRO,
                "confidence": 30 if not data.get("email") else 50,
                "source": "historical_import",
            },
        )
    if person:
        lead.primary_person_id = person.id
    if contact_name:
        db.add(Contact(
            lead_id=lead.id,
            name=contact_name,
            role=ContactRole.OUTRO,
            email=data.get("email") or None,
            phone=data.get("phone") or data.get("whatsapp") or None,
            linkedin_url=data.get("linkedin") or None,
            is_primary=True,
            confidence=50 if data.get("email") else 30,
            source="historical_import",
        ))
    db.flush()
    inspected.update({"lead": lead, "company": company, "person": person})
    return inspected


def _row_result(job: ImportJob, line_number: int, inspected: dict[str, Any]) -> ImportRowResult:
    return ImportRowResult(
        import_job_id=job.id,
        organization_id=job.organization_id,
        line_number=line_number,
        source_version=1,
        status=inspected["status"],
        reason_code=inspected.get("reason_code"),
        message=inspected.get("message"),
        lead_id=getattr(inspected.get("lead"), "id", None),
        company_id=getattr(inspected.get("company"), "id", None),
        person_id=getattr(inspected.get("person"), "id", None),
        identity_decision=inspected.get("identity_decision"),
        provenance={
            "source": "historical_import",
            "import_job_id": str(job.id),
            "line_number": line_number,
            "classification": "FACT" if inspected["status"] in (ImportRowStatus.ACCEPTED, ImportRowStatus.DUPLICATE) else "HYPOTHESIS",
        },
    )


def claim_next_import_job(db: Session) -> tuple[str, str] | None:
    """Reivindica um import com lock concorrente e workspace obrigatório."""
    cancel = _lock_query(db.query(ImportJob).filter(
        ImportJob.status == ImportJobStatus.CANCEL_REQUESTED,
        ImportJob.organization_id.is_not(None),
    ).order_by(ImportJob.created_at.asc()), skip_locked=True).first()
    if cancel:
        _transition(
            db,
            cancel,
            ImportJobStatus.CANCELLED,
            actor_id=None,
            expected_version=cancel.expected_version,
            allow_system=True,
            detail={"cancelled_by": "consumer"},
        )
        cancel.completed_at = _now()
        db.commit()
    job = _lock_query(db.query(ImportJob).filter(
        ImportJob.status == ImportJobStatus.QUEUED,
        ImportJob.organization_id.is_not(None),
    ).order_by(ImportJob.created_at.asc()), skip_locked=True).first()
    if not job:
        return None
    _transition(
        db,
        job,
        ImportJobStatus.RUNNING,
        actor_id=None,
        expected_version=job.expected_version,
        allow_system=True,
        detail={"attempt": job.attempts + 1, "claimed_by": "consumer"},
    )
    job.started_at = _now()
    job.attempts += 1
    db.commit()
    return str(job.id), str(job.organization_id)


def process_import_job(job_id: str, organization_id: str) -> None:
    """Processa lotes de até 1.000 linhas, cada lote em transação própria."""
    from src.db.session import SessionLocal
    db = SessionLocal()
    try:
        job = db.query(ImportJob).filter(
            ImportJob.id == job_id,
            ImportJob.organization_id == organization_id,
        ).first()
        if not job or job.status != ImportJobStatus.RUNNING:
            return
        done_lines = {
            row.line_number for row in db.query(ImportRowResult).filter(
                ImportRowResult.import_job_id == job.id,
                ImportRowResult.organization_id == job.organization_id,
                ImportRowResult.status != ImportRowStatus.FAILED,
            ).all()
        }
        pending = [
            (line, row) for line, row in enumerate(job.source_rows or [], start=2)
            if line not in done_lines
        ]
        job.unprocessed_rows = len(pending)
        db.commit()
        for start in range(0, len(pending), MAX_BATCH_SIZE):
            batch = pending[start:start + MAX_BATCH_SIZE]
            try:
                for line_number, raw_row in batch:
                    inspected = _inspect_row(db, job, raw_row)
                    inspected = _create_canonical_row(db, job, inspected, line_number)
                    db.add(_row_result(job, line_number, inspected))
                    status = inspected["status"]
                    if status == ImportRowStatus.ACCEPTED:
                        job.accepted_rows += 1
                    elif status == ImportRowStatus.DUPLICATE:
                        job.duplicate_rows += 1
                    elif status == ImportRowStatus.REJECTED:
                        job.rejected_rows += 1
                    else:
                        job.failed_rows += 1
                    job.unprocessed_rows = max(0, job.total_rows - job.accepted_rows - job.duplicate_rows - job.rejected_rows - job.failed_rows)
                db.commit()
            except Exception as exc:  # noqa: BLE001 — rollback integral do lote
                db.rollback()
                failed_job = db.query(ImportJob).filter(
                    ImportJob.id == job_id,
                    ImportJob.organization_id == organization_id,
                ).first()
                existing_lines = {item.line_number for item in db.query(ImportRowResult).filter(
                    ImportRowResult.import_job_id == job_id,
                    ImportRowResult.organization_id == organization_id,
                ).all()}
                for line_number, _ in batch:
                    if line_number not in existing_lines:
                        db.add(ImportRowResult(
                            import_job_id=job_id,
                            organization_id=organization_id,
                            line_number=line_number,
                            status=ImportRowStatus.FAILED,
                            reason_code="BATCH_FAILED",
                            message="Lote revertido; recovery autorizado pode tentar novamente.",
                            provenance={"source": "historical_import", "line_number": line_number},
                        ))
                failed_job.failed_rows += sum(1 for line_number, _ in batch if line_number not in existing_lines)
                failed_job.unprocessed_rows = max(0, failed_job.total_rows - failed_job.accepted_rows - failed_job.duplicate_rows - failed_job.rejected_rows - failed_job.failed_rows)
                failed_job.error_code = "RECOVERABLE_BATCH_FAILURE"
                failed_job.error_message = "Falha interna no lote; nenhum efeito parcial do lote foi mantido."
                failed_job.completed_at = _now()
                _transition(
                    db,
                    failed_job,
                    ImportJobStatus.FAILED,
                    actor_id=None,
                    expected_version=failed_job.expected_version,
                    allow_system=True,
                    detail={"attempt": failed_job.attempts, "batch_size": len(batch)},
                )
                db.commit()
                logger.exception("Falha no lote do import %s: %s", job_id, exc)
                return
            current = db.query(ImportJob).filter(ImportJob.id == job_id, ImportJob.organization_id == organization_id).first()
            if current and current.status == ImportJobStatus.CANCEL_REQUESTED:
                current.unprocessed_rows = max(0, current.total_rows - current.accepted_rows - current.duplicate_rows - current.rejected_rows - current.failed_rows)
                current.completed_at = _now()
                _transition(
                    db,
                    current,
                    ImportJobStatus.CANCELLED,
                    actor_id=None,
                    expected_version=current.expected_version,
                    allow_system=True,
                    detail={"cancelled_by": "consumer"},
                )
                db.commit()
                return
        final = db.query(ImportJob).filter(ImportJob.id == job_id, ImportJob.organization_id == organization_id).first()
        if not final or final.status != ImportJobStatus.RUNNING:
            return
        final.completed_at = _now()
        target = ImportJobStatus.PARTIAL if final.rejected_rows or final.failed_rows else ImportJobStatus.SUCCEEDED
        _transition(
            db,
            final,
            target,
            actor_id=None,
            expected_version=final.expected_version,
            allow_system=True,
            detail={
                "accepted": final.accepted_rows,
                "duplicate": final.duplicate_rows,
                "rejected": final.rejected_rows,
                "failed": final.failed_rows,
            },
        )
        final.unprocessed_rows = 0
        db.commit()
    finally:
        db.close()
