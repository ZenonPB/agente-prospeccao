"""Regressão de `change-password`: a rota validava a senha atual mas nunca
gravava a nova hash nem fazia commit — a senha não mudava de fato."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.auth.security import hash_password, verify_password
from src.routes.auth import ChangePasswordRequest, change_password


def _request():
    # Sem limiter no app.state → o decorador slowapi passa direto.
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(limiter=None)))


def test_change_password_persiste_nova_hash():
    user = SimpleNamespace(
        password_hash=hash_password("senha-antiga"),
        email="u@test.local",
    )
    commits = []
    db = SimpleNamespace(commit=lambda: commits.append(True))

    body = ChangePasswordRequest(current_password="senha-antiga", new_password="nova-senha-123")
    change_password(request=_request(), body=body, db=db, current_user=user)

    assert verify_password("nova-senha-123", user.password_hash)
    assert not verify_password("senha-antiga", user.password_hash)
    assert commits == [True]


def test_change_password_senha_atual_errada_nao_altera():
    user = SimpleNamespace(
        password_hash=hash_password("senha-antiga"),
        email="u@test.local",
    )
    db = SimpleNamespace(commit=lambda: None)
    body = ChangePasswordRequest(current_password="errada", new_password="nova-senha-123")

    with pytest.raises(HTTPException) as exc:
        change_password(request=_request(), body=body, db=db, current_user=user)
    assert exc.value.status_code == 400
    assert verify_password("senha-antiga", user.password_hash)