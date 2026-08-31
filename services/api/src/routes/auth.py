"""Rotas de autenticação: registro, login, recuperação de senha."""
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from src.db.dependencies import get_db
from src.db.models import User, OnboardingStatus
from src.auth.security import hash_password, verify_password, create_access_token
from src.auth.dependencies import get_current_user
from src.middleware.rate_limit import limiter
from src.config.settings import settings
from src.services.email_service import send_password_reset_email
from src.services.org_service import create_personal_organization

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Lockout simples em memória (adequado para deploy single-process em tier grátis).
# Chave: email normalizado → (tentativas_falhas, timestamp_última_tentativa).
_login_attempts: dict[str, tuple[int, float]] = {}
_LOCKOUT_THRESHOLD = 5
_LOCKOUT_SECONDS = 900  # 15 minutos


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user: dict
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UpdateProfileRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)


class UpdateOnboardingStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(NOT_STARTED|IN_PROGRESS|COMPLETED|DISMISSED)$")


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    """Registra um novo usuário com email e senha."""
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma conta com este email",
        )

    user = User(
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
        role="SALES",
    )
    db.add(user)
    db.flush()

    # Onboarding multi-tenant: cada usuário nasce com um workspace pessoal.
    create_personal_organization(db, user)

    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "email": user.email})

    return {
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "onboarding_status": user.onboarding_status.value if hasattr(user.onboarding_status, "value") else str(user.onboarding_status or "NOT_STARTED"),
        },
        "token": token,
    }


@router.post("/login", response_model=AuthResponse)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    """Login com email e senha, retorna um token JWT."""
    email_key = body.email.lower().strip()

    # Account lockout: verifica se excedeu tentativas
    if email_key in _login_attempts:
        fails, last_ts = _login_attempts[email_key]
        if fails >= _LOCKOUT_THRESHOLD:
            elapsed = time.monotonic() - last_ts
            if elapsed < _LOCKOUT_SECONDS:
                remaining = int(_LOCKOUT_SECONDS - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Muitas tentativas. Tente novamente em {remaining // 60}min.",
                )
            _login_attempts.pop(email_key, None)

    user = db.query(User).filter(User.email == email_key).first()
    if not user or not verify_password(body.password, user.password_hash):
        # Registra tentativa falha
        fails, _ = _login_attempts.get(email_key, (0, 0.0))
        _login_attempts[email_key] = (fails + 1, time.monotonic())
        logger.warning("Login falhou para %s (tentativa %d)", email_key, fails + 1)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
        )

    # Login bem-sucedido: reseta contador
    _login_attempts.pop(email_key, None)

    token = create_access_token({"sub": str(user.id), "email": user.email})

    return {
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "onboarding_status": user.onboarding_status.value if hasattr(user.onboarding_status, "value") else str(user.onboarding_status or "NOT_STARTED"),
        },
        "token": token,
    }


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
def forgot_password(request: Request, body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Solicita redefinição de senha. Envia email com link contendo token."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        return {"message": "Se o email existir, você receberá um link de redefinição."}

    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.RESET_TOKEN_EXPIRY_HOURS)

    user.reset_token = token
    user.reset_token_expires = expires_at
    db.commit()

    reset_link = f"{settings.APP_BASE_URL}/resetar-senha?token={token}"

    send_password_reset_email(user.email, reset_link, user.name)

    return {"message": "Se o email existir, você receberá um link de redefinição."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
def reset_password(request: Request, body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Redefine a senha usando um token válido."""
    user = db.query(User).filter(
        User.reset_token == body.token,
        User.reset_token_expires > datetime.now(timezone.utc),
    ).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token inválido ou expirado.",
        )

    user.password_hash = hash_password(body.password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()

    return {"message": "Senha redefinida com sucesso."}


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    request: Request,
    body: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Altera a senha do usuário autenticado."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta.",
        )

    current_user.password_hash = hash_password(body.new_password)
    current_user.reset_token = None
    current_user.reset_token_expires = None
    db.commit()
    logger.info("Password changed for user %s", current_user.email)
    return {"message": "Senha alterada com sucesso."}


@router.patch("/profile")
def update_profile(
    request: Request,
    body: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Atualiza o perfil do usuário autenticado."""
    current_user.name = body.name
    db.commit()
    db.refresh(current_user)

    return {
        "id": str(current_user.id),
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
    }


@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user),
):
    """Retorna os dados do usuário autenticado."""
    status_val = current_user.onboarding_status.value if hasattr(current_user.onboarding_status, "value") else str(current_user.onboarding_status or "NOT_STARTED")
    return {
        "id": str(current_user.id),
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
        "onboarding_status": status_val,
    }


@router.patch("/onboarding")
def update_onboarding_status(
    body: UpdateOnboardingStatusRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Atualiza o status de onboarding do usuário."""
    current_user.onboarding_status = OnboardingStatus[body.status]
    db.commit()
    db.refresh(current_user)
    status_val = current_user.onboarding_status.value if hasattr(current_user.onboarding_status, "value") else str(current_user.onboarding_status)
    return {
        "id": str(current_user.id),
        "onboarding_status": status_val,
    }
