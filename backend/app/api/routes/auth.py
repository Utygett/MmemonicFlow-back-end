import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import verify_password, hash_password, get_current_user, get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.auth.jwt import create_access_token, create_refresh_token, decode_refresh_token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from app.core.email import send_email, build_verification_email, build_password_reset_email
from app.core.config import settings
from app.schemas.auth import RegisterResponse

router = APIRouter(tags=["auth"])
security = HTTPBearer()


# --- Схемы для новых эндпоинтов ---
class RequestPasswordResetRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    token: str


# --- Существующие эндпоинты ---
@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(data: RegisterRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    verification_token = secrets.token_urlsafe(32)
    verification_expires = datetime.now(timezone.utc) + timedelta(hours=24)

    user = User(
        id=uuid4(),
        username="user",
        email=email,
        password_hash=hash_password(data.password),
        is_email_verified=False,
        email_verification_token=verification_token,
        email_verification_expires=verification_expires,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Отправка письма с подтверждением
    html = build_verification_email(verification_token, settings.FRONTEND_URL)
    try:
        await send_email(user.email, "Подтверждение регистрации", html)
    except Exception as e:
        # Логируй ошибку, но не прерывай регистрацию
        print(f"Failed to send verification email: {e}")

    return RegisterResponse(
        message="Регистрация успешна. Подтвердите email и затем войдите.",
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS", "message": "invalid login or pass"})

    # Опционально: блокируй вход, если email не подтверждён
    if not user.is_email_verified:
         raise HTTPException(status_code=403, detail={"code": "EMAIL_NOT_VERIFIED", "message": "email not verified"})

    access = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=access,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_refresh_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_access = create_access_token({"sub": sub})
    return TokenResponse(
        access_token=new_access,
        refresh_token=credentials.credentials,
        token_type="bearer",
    )


# --- Новые эндпоинты ---
@router.post("/verify-email", status_code=200)
def verify_email(data: VerifyEmailRequest, db: Session = Depends(get_db)):
    """
    Подтверждение email пользователя по токену из письма.
    """
    user = db.query(User).filter(User.email_verification_token == data.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    if user.email_verification_expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")

    user.is_email_verified = True
    user.email_verification_token = None
    user.email_verification_expires = None
    db.commit()

    return {"message": "Email verified successfully"}


@router.post("/request-password-reset", status_code=200)
async def request_password_reset(data: RequestPasswordResetRequest, db: Session = Depends(get_db)):
    """
    Запрос на восстановление пароля: отправляет письмо с токеном.
    """
    email = data.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    # Не раскрываем, существует ли email (защита от перебора)
    if not user:
        return {"message": "If this email exists, a reset link has been sent"}

    # Генерация токена сброса
    reset_token = secrets.token_urlsafe(32)
    reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)

    user.password_reset_token = reset_token
    user.password_reset_expires = reset_expires
    db.commit()

    # Отправка письма
    html = build_password_reset_email(reset_token, settings.FRONTEND_URL)
    try:
        await send_email(user.email, "Восстановление пароля", html)
    except Exception as e:
        print(f"Failed to send password reset email: {e}")

    return {"message": "If this email exists, a reset link has been sent"}


@router.post("/reset-password", status_code=200)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """
    Установка нового пароля по токену из письма.
    """
    user = db.query(User).filter(User.password_reset_token == data.token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    if user.password_reset_expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Token expired")

    # Устанавливаем новый пароль
    user.password_hash = hash_password(data.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    db.commit()

    return {"message": "Password reset successfully"}
