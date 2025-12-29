import uuid as uuidlib
from fastapi.testclient import TestClient


class TestRegister:
    def test_register_success(self, client: TestClient):
        resp = client.post(
            "/api/auth/register",
            json={"email": f"newuser_{uuidlib.uuid4()}@example.com", "password": "password123"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_register_existing_email(self, client: TestClient):
        email = f"duplicate_{uuidlib.uuid4()}@example.com"
        r1 = client.post("/api/auth/register", json={"email": email, "password": "password123"})
        assert r1.status_code == 200, r1.text

        r2 = client.post("/api/auth/register", json={"email": email, "password": "password456"})
        assert r2.status_code == 400, r2.text

    def test_register_invalid_email(self, client: TestClient):
        resp = client.post("/api/auth/register", json={"email": "invalid-email", "password": "password123"})
        assert resp.status_code == 422, resp.text

    def test_register_short_password(self, client: TestClient):
        resp = client.post("/api/auth/register", json={"email": f"t_{uuidlib.uuid4()}@example.com", "password": "pass"})
        assert resp.status_code == 422, resp.text


class TestLogin:
    def test_login_success(self, client: TestClient):
        email = f"logintest_{uuidlib.uuid4()}@example.com"
        reg = client.post("/api/auth/register", json={"email": email, "password": "password123"})
        assert reg.status_code == 200, reg.text

        resp = client.post("/api/auth/login", json={"email": email, "password": "password123"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_password(self, client: TestClient):
        email = f"wrongpass_{uuidlib.uuid4()}@example.com"
        reg = client.post("/api/auth/register", json={"email": email, "password": "password123"})
        assert reg.status_code == 200, reg.text

        resp = client.post("/api/auth/login", json={"email": email, "password": "wrongpassword"})
        assert resp.status_code == 401, resp.text

    def test_login_nonexistent_email(self, client: TestClient):
        resp = client.post(
            "/api/auth/login",
            json={"email": f"nonexistent_{uuidlib.uuid4()}@example.com", "password": "password123"},
        )
        assert resp.status_code == 401, resp.text


class TestGetCurrentUser:
    def test_me_success(self, client: TestClient):
        email = f"metest_{uuidlib.uuid4()}@example.com"
        reg = client.post("/api/auth/register", json={"email": email, "password": "password123"})
        assert reg.status_code == 200, reg.text
        token = reg.json()["access_token"]

        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "id" in data
        assert data["email"] == email

    def test_me_no_token(self, client: TestClient):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401, resp.text

    def test_me_invalid_token(self, client: TestClient):
        resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalidtoken"})
        assert resp.status_code == 401, resp.text


class TestRefreshToken:
    def test_refresh_success(self, client: TestClient):
        email = f"refreshtest_{uuidlib.uuid4()}@example.com"
        reg = client.post("/api/auth/register", json={"email": email, "password": "password123"})
        assert reg.status_code == 200, reg.text
        refresh = reg.json()["refresh_token"]

        resp = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {refresh}"})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_refresh_invalid_token(self, client: TestClient):
        resp = client.post("/api/auth/refresh", headers={"Authorization": "Bearer invalidtoken"})
        assert resp.status_code == 401, resp.text

    def test_refresh_no_token(self, client: TestClient):
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 401, resp.text

    def test_new_access_token_works(self, client: TestClient):
        email = f"newtoken_{uuidlib.uuid4()}@example.com"
        reg = client.post("/api/auth/register", json={"email": email, "password": "password123"})
        assert reg.status_code == 200, reg.text
        refresh = reg.json()["refresh_token"]

        refresh_resp = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {refresh}"})
        assert refresh_resp.status_code == 200, refresh_resp.text
        new_access = refresh_resp.json()["access_token"]

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access}"})
        assert me.status_code == 200, me.text
        assert "id" in me.json()
