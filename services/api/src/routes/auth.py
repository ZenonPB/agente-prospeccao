"""Rotas de autenticação: registro, login, recuperação de senha."""
import logging
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from src.db.dependencies import get_db
from src.db.models import User
from src.auth.security import hash_password, verify_password, create_access_token
from src.auth.dependencies import get_current_user
from src.middleware.rate_limit import limiter
from src.config.settings import settings
from src.services.email_service import send_password_reset_email
from src.services.org_service import create_personal_organization

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


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
        },
        "token": token,
    }


@router.post("/login", response_model=AuthResponse)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    """Login com email e senha, retorna um token JWT."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
        )

    token = create_access_token({"sub": str(user.id), "email": user.email})

    return {
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
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
