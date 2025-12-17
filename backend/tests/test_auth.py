import pytest
from app.main import app
from fastapi.testclient import TestClient
from app.models.user import User
from app.core.security import hash_password
from uuid import uuid4
from app.db.session import SessionLocal

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def test_user():
    db = SessionLocal()
    user = User(
        id=uuid4(),
        email="existing@test.com",
        username="existing_user",
        password_hash=hash_password("password123")
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.delete(user)
    db.commit()


def test_register_success(client):
    response = client.post(
        "/auth/register",  # <-- тут обязательно /auth
        json={
            "email": "new@test.com",
            "password": "password123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_register_duplicate_email(client, test_user):
    response = client.post(
        "/auth/register",
        json={
            "email": test_user.email,
            "password": "password123",
        },
    )
    assert response.status_code == 400


def test_login_success(client, test_user):
    response = client.post(
        "/auth/login",
        json={
            "email": test_user.email,
            "password": "password123",
        },
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password(client, test_user):
    response = client.post(
        "/auth/login",
        json={
            "email": test_user.email,
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401
