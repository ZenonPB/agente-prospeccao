"""Lockout de login persistente em banco.

Substitui o dict em memória que vivia em `routes/auth.py` (quebrado em
multi-processo e perdido a cada restart). O estado vive na tabela
`login_attempts` (uma linha por e-mail normalizado), logo é compartilhado
entre processos e sobrevive a restart.

As funções operam sobre uma sessão SQLAlchemy qualquer — em produção a
sessão real, nos testes uma fake com `query/add/delete/commit`.
"""
import logging
from datetime import datetime, timedelta, timezone

from src.db.models import LoginAttempt

logger = logging.getLogger(__name__)

LOGIN_LOCKOUT_THRESHOLD = 5
LOCKOUT_WINDOW = timedelta(minutes=15)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.lower().strip()


def is_locked(db, email: str, *, now: datetime | None = None) -> tuple[bool, int]:
    """Diz se o e-mail está bloqueado e quantos segundos restam (0 se livre)."""
    now = now or utcnow()
    row = db.query(LoginAttempt).filter(LoginAttempt.email == normalize_email(email)).first()
    if row is None or row.locked_until is None:
        return False, 0
    locked_until = row.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    remaining = int((locked_until - now).total_seconds())
    if remaining <= 0:
        return False, 0
    return True, remaining


def register_failure(db, email: str, *, now: datetime | None = None) -> None:
    """Registra uma falha; ao atingir o limite, arma `locked_until`."""
    now = now or utcnow()
    key = normalize_email(email)
    row = db.query(LoginAttempt).filter(LoginAttempt.email == key).first()
    if row is None:
        row = LoginAttempt(email=key, failed_count=0, last_attempt_at=now)
        db.add(row)
    row.failed_count = int(row.failed_count or 0) + 1
    row.last_attempt_at = now
    if row.failed_count >= LOGIN_LOCKOUT_THRESHOLD and not _still_locked(row, now):
        row.locked_until = now + LOCKOUT_WINDOW
    db.commit()


def clear_attempts(db, email: str) -> None:
    """Limpa o contador após um login bem-sucedido."""
    key = normalize_email(email)
    row = db.query(LoginAttempt).filter(LoginAttempt.email == key).first()
    if row is not None:
        db.delete(row)
        db.commit()


def _still_locked(row: LoginAttempt, now: datetime) -> bool:
    if row.locked_until is None:
        return False
    locked_until = row.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return locked_until > now
