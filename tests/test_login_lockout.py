"""Lockout de login persistente em banco (hardening — quebra do single-process).

O lockout vivia num dict em memória (`_login_attempts` em `routes/auth.py`),
que não sobrevive a restart nem funciona em multi-processo. A fonte passa a
ser a tabela `login_attempts`, acessada pelo seam
`src.services.login_lockout_service` (puro em cima de uma sessão — testável
com sessão fake, sem Postgres).

Cobre: bloqueio após N falhas, limpeza no sucesso, expiração da janela,
normalização do e-mail e o ciclo HTTP completo via `login()` com sessão fake.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.auth.security import hash_password
from src.db.models import LoginAttempt, User
from src.routes import auth as auth_module
from src.routes.auth import LoginRequest, login
from src.services import login_lockout_service as lockout


EMAIL = "Dev@Exemplo.com.br"


class _FakeQ:
    def __init__(self, result=None):
        self._result = result

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self._result


class _FakeDb:
    """Sessão fake: User fixo + tabela login_attempts num dict (o 'banco')."""

    def __init__(self, user=None):
        self.user = user
        self.attempts: dict[str, LoginAttempt] = {}
        self.commits = 0

    def query(self, model):
        if model is User:
            return _FakeQ(self.user)
        if model is LoginAttempt:
            rows = list(self.attempts.values())
            return _FakeQ(rows[0] if rows else None)
        return _FakeQ(None)

    def add(self, obj):
        if isinstance(obj, LoginAttempt):
            self.attempts[obj.email] = obj

    def delete(self, obj):
        if isinstance(obj, LoginAttempt):
            self.attempts.pop(obj.email, None)

    def commit(self):
        self.commits += 1


def _request():
    # Sem limiter no app.state → o decorador slowapi passa direto.
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(limiter=None)))


def _call_login(db, email, password):
    """Chama a função nua da rota (sem o `limiter` — lockout, não rate-limit)."""
    raw = getattr(login, "__wrapped__", login)
    return raw(request=_request(), body=LoginRequest(email=email, password=password), db=db)


def _user(password="senha-correta-123"):
    return SimpleNamespace(
        id="u-1",
        name="Dev",
        email="dev@exemplo.com.br",
        password_hash=hash_password(password),
        role="SALES",
        onboarding_status="NOT_STARTED",
    )


def _wrong_login(db, email=EMAIL):
    with pytest.raises(HTTPException) as exc:
        _call_login(db, email, "errada")
    return exc.value


# ---------- seam de serviço ----------


def test_falhas_abaixo_do_limite_nao_bloqueiam():
    db = _FakeDb()
    for _ in range(lockout.LOGIN_LOCKOUT_THRESHOLD - 1):
        lockout.register_failure(db, EMAIL)
    locked, _remaining = lockout.is_locked(db, EMAIL)
    assert locked is False


def test_limite_de_falhas_bloqueia():
    db = _FakeDb()
    for _ in range(lockout.LOGIN_LOCKOUT_THRESHOLD):
        lockout.register_failure(db, EMAIL)
    locked, remaining = lockout.is_locked(db, EMAIL)
    assert locked is True
    assert remaining > 0


def test_sucesso_limpa_o_contador():
    db = _FakeDb()
    for _ in range(lockout.LOGIN_LOCKOUT_THRESHOLD):
        lockout.register_failure(db, EMAIL)
    assert lockout.is_locked(db, EMAIL)[0] is True
    lockout.clear_attempts(db, EMAIL)
    assert lockout.is_locked(db, EMAIL)[0] is False


def test_bloqueio_expira_apos_a_janela():
    db = _FakeDb()
    for _ in range(lockout.LOGIN_LOCKOUT_THRESHOLD):
        lockout.register_failure(db, EMAIL)
    row = db.attempts[EMAIL.lower()]
    row.locked_until = lockout.utcnow() - lockout.LOCKOUT_WINDOW
    locked, _remaining = lockout.is_locked(db, EMAIL)
    assert locked is False


def test_email_normalizado_case_insensitive():
    db = _FakeDb()
    lockout.register_failure(db, "  DEV@Exemplo.COM.BR ")
    assert list(db.attempts) == [EMAIL.lower()]
    locked_before, _ = lockout.is_locked(db, "dev@exemplo.com.br")
    assert locked_before is False
    for _ in range(lockout.LOGIN_LOCKOUT_THRESHOLD - 1):
        lockout.register_failure(db, EMAIL.lower())
    assert lockout.is_locked(db, EMAIL)[0] is True


# ---------- ciclo HTTP via login() ----------


def test_login_bloqueia_apos_cinco_falhas_e_devolve_429():
    db = _FakeDb(user=_user())
    for _ in range(5):
        assert _wrong_login(db).status_code == 401
    err = _wrong_login(db)
    assert err.status_code == 429


def test_login_com_senha_correta_limpa_falhas_anteriores():
    db = _FakeDb(user=_user())
    for _ in range(4):
        assert _wrong_login(db).status_code == 401
    ok = _call_login(db, EMAIL, "senha-correta-123")
    assert ok["token"]
    # Contador zerado: a próxima falha volta a ser 401, não 429.
    assert _wrong_login(db).status_code == 401


def test_lockout_nao_usa_dict_em_memoria():
    """Prova de persistência: o dict legado do módulo fica vazio; o estado
    vive na sessão (banco), logo sobrevive a restart e a multi-processo."""
    auth_module._login_attempts.clear()
    db = _FakeDb(user=_user())
    for _ in range(5):
        _wrong_login(db)
    assert auth_module._login_attempts == {}
    assert list(db.attempts) == [EMAIL.lower()]
    assert _wrong_login(db).status_code == 429
