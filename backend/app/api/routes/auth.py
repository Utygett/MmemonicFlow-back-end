from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from datetime import datetime, timedelta, timezone
from app.core.config import settings
from app.core.security import verify_password
from app.schemas.auth import LoginRequest, TokenResponse
from app.core.security import verify_password
from app.core.security import hash_password
from fastapi import Depends
from jose import JWTError, jwt
from app.schemas.auth import RegisterRequest
from app.core.security import get_current_user
from app.schemas.auth import UserResponse

router = APIRouter(tags=["auth"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user




@router.post("/register", response_model=TokenResponse)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    lower_email = data.email.lower()
    existing_user = db.query(User).filter(User.email == lower_email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    user = User(
        id=uuid4(),
        username="user",
        email=lower_email,
        password_hash=hash_password(data.password),
        # created_at=datetime.now(timezone.utc),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})

    return {
        "access_token": token,
        "token_type": "bearer",
    }



@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    lower_email = data.email.lower()
    user = db.query(User).filter(User.email == lower_email).first()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(data={"sub": str(user.id)})

    return {
        "access_token": token,
        "token_type": "bearer",
    }

def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    return encoded_jwt