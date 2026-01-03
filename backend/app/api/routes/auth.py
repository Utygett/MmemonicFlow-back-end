from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import verify_password, hash_password, get_current_user, get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.auth.jwt import create_access_token, create_refresh_token, decode_refresh_token
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter(tags=["auth"])
security = HTTPBearer()


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/register", response_model=TokenResponse)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    user = User(
        id=uuid4(),
        username="user",
        email=data.email,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        token_type="bearer",
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access = create_access_token({"sub": str(user.id)})
    refresh = create_refresh_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
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
    # refresh не меняем, просто возвращаем новый access
    return TokenResponse(
        access_token=new_access,
        refresh_token=credentials.credentials,  # старый refresh тоже возвращаем
        token_type="bearer",
    )
