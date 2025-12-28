import uuid as uuid_lib
import pytest
import uuid as uuid_lib
from fastapi.testclient import TestClient

class TestRegister:
    """Тесты регистрации."""

    def test_register_success(self, client: TestClient):
        """Успешная регистрация возвращает access и refresh токены."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": f"newuser_{uuid_lib.uuid4()}@example.com",  # ← Уникальный
                "password": "password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_register_existing_email(self, client: TestClient):
        """Регистрация с существующим email возвращает 400."""
        unique_email = f"duplicate_{uuid_lib.uuid4()}@example.com"

        # Сначала регистрируем пользователя
        client.post(
            "/api/auth/register",
            json={
                "email": unique_email,
                "password": "password123",
            },
        )
        # Пытаемся зарегистрировать с тем же email
        response = client.post(
            "/api/auth/register",
            json={
                "email": unique_email,  # ← Одинаковый в одном тесте
                "password": "password456",
            },
        )
        assert response.status_code == 400

    def test_register_invalid_email(self, client: TestClient):
        """Невалидный email возвращает 422."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "invalid-email",
                "password": "password123",
            },
        )
        assert response.status_code == 422

    def test_register_short_password(self, client: TestClient):
        """Пароль короче 6 символов возвращает 422."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": f"test_{uuid_lib.uuid4()}@example.com",  # ← Уникальный
                "password": "pass",
            },
        )
        assert response.status_code == 422


class TestLogin:
    """Тесты логина."""

    def test_login_success(self, client: TestClient):
        """Успешный логин возвращает access и refresh токены."""
        unique_email = f"login_test_{uuid_lib.uuid4()}@example.com"

        # Регистрируемся
        client.post(
            "/api/auth/register",
            json={
                "email": unique_email,
                "password": "password123",
            },
        )
        # Логинимся
        response = client.post(
            "/api/auth/login",
            json={
                "email": unique_email,
                "password": "password123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_password(self, client: TestClient):
        """Неверный пароль возвращает 401."""
        unique_email = f"wrong_pass_{uuid_lib.uuid4()}@example.com"

        # Регистрируемся
        client.post(
            "/api/auth/register",
            json={
                "email": unique_email,
                "password": "password123",
            },
        )
        # Пытаемся логиниться с неверным паролем
        response = client.post(
            "/api/auth/login",
            json={
                "email": unique_email,
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401

    def test_login_nonexistent_email(self, client: TestClient):
        """Логин с несуществующим email возвращает 401."""
        response = client.post(
            "/api/auth/login",
            json={
                "email": f"nonexistent_{uuid_lib.uuid4()}@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 401


class TestGetCurrentUser:
    """Тесты получения текущего пользователя."""

    def test_get_me_success(self, client: TestClient):
        """Получение текущего пользователя с валидным токеном."""
        unique_email = f"me_test_{uuid_lib.uuid4()}@example.com"

        # Регистрируемся и берём токен
        reg_response = client.post(
            "/api/auth/register",
            json={
                "email": unique_email,
                "password": "password123",
            },
        )
        token = reg_response.json()["access_token"]

        # Запрашиваем /me с этим токеном
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["email"] == unique_email

    def test_get_me_no_token(self, client: TestClient):
        """Запрос без токена возвращает 401."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_get_me_invalid_token(self, client: TestClient):
        """Запрос с невалидным токеном возвращает 401."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401


class TestRefreshToken:
    """Тесты обновления access токена."""

    def test_refresh_success(self, client: TestClient):
        """Успешное обновление access токена через refresh."""
        unique_email = f"refresh_test_{uuid_lib.uuid4()}@example.com"

        # Регистрируемся
        reg_response = client.post(
            "/api/auth/register",
            json={
                "email": unique_email,
                "password": "password123",
            },
        )
        refresh = reg_response.json()["refresh_token"]

        # Обновляем через refresh
        response = client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_refresh_with_invalid_token(self, client: TestClient):
        """Refresh с невалидным токеном возвращает 401."""
        response = client.post(
            "/api/auth/refresh",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code == 401

    def test_refresh_no_token(self, client: TestClient):
        """Refresh без токена возвращает 401."""
        response = client.post("/api/auth/refresh")
        assert response.status_code == 401

    def test_new_access_token_works(self, client: TestClient):
        """Новый access токен из refresh работает для /me."""
        unique_email = f"new_token_{uuid_lib.uuid4()}@example.com"

        # Регистрируемся
        reg_response = client.post(
            "/api/auth/register",
            json={
                "email": unique_email,
                "password": "password123",
            },
        )
        refresh = reg_response.json()["refresh_token"]

        # Обновляем токен
        refresh_response = client.post(
            "/api/auth/refresh",
            headers={"Authorization": f"Bearer {refresh}"},
        )
        new_access = refresh_response.json()["access_token"]

        # Используем новый токен в /me
        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {new_access}"},
        )
        assert me_response.status_code == 200
        assert "id" in me_response.json()
