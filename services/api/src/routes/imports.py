"""API tenant-safe do Historical Importer CSV/XLSX."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, get_user_membership, get_user_organization
from src.db.dependencies import get_db
from src.db.models import Organization, OrganizationMember, User
from src.middleware.rate_limit import limiter
from src.services.org_service import is_full_access
from src.services.import_job_service import (
    ImportJobError,
    cancel,
    confirm,
    create_preview,
    dry_run,
    get_job,
    list_rows,
    recover,
    serialize_job,
)
from src.services.historical_import_parser import MAX_FILE_BYTES

router = APIRouter(prefix="/imports", tags=["imports"])


class MappingRequest(BaseModel):
    mapping: dict[str, str | None]
    expected_version: int = Field(..., ge=1)


class ConfirmRequest(MappingRequest):
    mapping_version: str = Field(..., min_length=8, max_length=64)
    idempotency_key: str = Field(..., min_length=1, max_length=255)


class VersionRequest(BaseModel):
    expected_version: int = Field(..., ge=1)


def _raise(error: ImportJobError) -> None:
    raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message})


def _assert_job_scope(job: Any, user: User, member: OrganizationMember) -> None:
    if not is_full_access(member) and str(job.actor_id) != str(user.id):
        raise HTTPException(status_code=404, detail="Importação não encontrada")


def _confirmed_replay(
    db: Session,
    org_id: Any,
    import_id: str,
    body: ConfirmRequest,
    user: User,
    member: OrganizationMember,
):
    """Reconhece retry idempotente após uma corrida de confirmação.

    ``confirm`` protege a escrita com lock/versionamento. Se outra request vencer
    a corrida, esta request pode carregar uma versão antiga. Depois do rollback
    relemos o job e só aceitamos replay quando chave *e* mapping são exatamente
    os já persistidos, evitando transformar VERSION_CONFLICT real em sucesso.
    """
    current = get_job(db, org_id, import_id)
    _assert_job_scope(current, user, member)
    if (
        current.idempotency_key == body.idempotency_key
        and current.mapping_version == body.mapping_version
        and current.status.value in {"QUEUED", "RUNNING", "SUCCEEDED", "PARTIAL", "FAILED", "CANCEL_REQUESTED", "CANCELLED"}
    ):
        return current
    return None


@router.post("", status_code=201)
@limiter.limit("10/minute")
def upload_import(
    request: Request,
    file: UploadFile = File(...),
    campaign_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(get_user_membership),
):
    """Valida e cria um preview sem efeitos comerciais.

    O preview é deliberadamente descartável e pode ser repetido; a fronteira
    idempotente do import é a confirmação, onde a chave passa a ser persistida
    e protegida por UNIQUE por workspace. Isso evita prometer idempotência de
    upload enquanto o usuário ainda pode trocar mapping/dry-run.
    """
    content = file.file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        _raise(ImportJobError("FILE_TOO_LARGE", "O arquivo excede o limite de 25 MiB.", 413))
    try:
        job = create_preview(
            db,
            organization_id=_org.id,
            actor_id=user.id,
            content=content,
            filename=file.filename,
            content_type=file.content_type,
            campaign_id=campaign_id,
            idempotency_key=None,
            correlation_id=request.headers.get("X-Request-ID"),
            member=_member,
        )
    except ImportJobError as error:
        _raise(error)
    return serialize_job(job)


@router.get("/{import_id}")
def read_import(
    import_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(get_user_membership),
):
    try:
        job = get_job(db, _org.id, import_id)
        _assert_job_scope(job, _user, _member)
        return serialize_job(job)
    except ImportJobError as error:
        _raise(error)


@router.get("/{import_id}/rows")
def read_import_rows(
    import_id: str,
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=1000, ge=1, le=1000),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(get_user_membership),
):
    try:
        job = get_job(db, _org.id, import_id)
        _assert_job_scope(job, _user, _member)
        return list_rows(db, _org.id, import_id, status=status, offset=offset, limit=limit)
    except ImportJobError as error:
        _raise(error)


@router.post("/{import_id}/dry-run")
def dry_run_import(
    import_id: str,
    body: MappingRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(get_user_membership),
):
    try:
        _assert_job_scope(get_job(db, _org.id, import_id), user, _member)
        return dry_run(db, _org.id, user.id, import_id, body.mapping, body.expected_version, _member)
    except ImportJobError as error:
        _raise(error)


@router.post("/{import_id}/confirm")
def confirm_import(
    import_id: str,
    body: ConfirmRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(get_user_membership),
):
    try:
        _assert_job_scope(get_job(db, _org.id, import_id), user, _member)
        job = confirm(
            db, _org.id, user.id, import_id, body.mapping, body.mapping_version,
            body.expected_version, body.idempotency_key, _member,
        )
        return serialize_job(job, include_preview=False)
    except ImportJobError as error:
        if error.code in {"VERSION_CONFLICT", "IDEMPOTENCY_CONFLICT"}:
            db.rollback()
            try:
                replay = _confirmed_replay(db, _org.id, import_id, body, user, _member)
            except ImportJobError:
                replay = None
            if replay is not None:
                return serialize_job(replay, include_preview=False)
        _raise(error)


@router.post("/{import_id}/cancel")
def cancel_import(
    import_id: str,
    body: VersionRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(get_user_membership),
):
    try:
        current = get_job(db, _org.id, import_id)
        _assert_job_scope(current, user, _member)
        job = cancel(db, _org.id, user.id, import_id, body.expected_version if body else None, _member)
        return serialize_job(job, include_preview=False)
    except ImportJobError as error:
        _raise(error)


@router.post("/{import_id}/recover")
def recover_import(
    import_id: str,
    body: VersionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _org: Organization = Depends(get_user_organization),
    _member: OrganizationMember = Depends(get_user_membership),
):
    try:
        _assert_job_scope(get_job(db, _org.id, import_id), user, _member)
        job = recover(db, _org.id, user.id, import_id, body.expected_version, _member)
        return serialize_job(job, include_preview=False)
    except ImportJobError as error:
        _raise(error)
