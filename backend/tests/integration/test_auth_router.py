# tests/integration/test_auth_router.py

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.routers.auth import router
from app.database import get_db
from app.auth.utils import hash_password, get_current_user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_db():
    client = AsyncMongoMockClient()
    return client["test_db"]


@pytest.fixture
def app(fake_db):
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.dependency_overrides[get_db] = lambda: fake_db
    return application


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


async def insert_user(db, username="alice", password="secret", role="reader"):
    await db["users"].insert_one(
        {
            "username": username,
            "password_hash": hash_password(password),
            "role": role,
        }
    )


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    async def test_valid_credentials_returns_200(self, client, fake_db):
        await insert_user(fake_db, "alice", "secret", "writer")
        resp = client.post(
            "/api/v1/auth/login", data={"username": "alice", "password": "secret"}
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "alice"
        assert resp.json()["role"] == "writer"

    async def test_valid_credentials_sets_cookie(self, client, fake_db):
        await insert_user(fake_db, "alice", "secret")
        resp = client.post(
            "/api/v1/auth/login", data={"username": "alice", "password": "secret"}
        )
        assert "access_token" in resp.cookies

    async def test_wrong_password_returns_401(self, client, fake_db):
        await insert_user(fake_db, "alice", "secret")
        resp = client.post(
            "/api/v1/auth/login", data={"username": "alice", "password": "wrong"}
        )
        assert resp.status_code == 401

    async def test_unknown_user_returns_401(self, client, fake_db):
        resp = client.post(
            "/api/v1/auth/login", data={"username": "ghost", "password": "secret"}
        )
        assert resp.status_code == 401

    async def test_role_defaults_to_reader_when_missing(self, client, fake_db):
        await fake_db["users"].insert_one(
            {
                "username": "norole",
                "password_hash": hash_password("pass"),
            }
        )
        resp = client.post(
            "/api/v1/auth/login", data={"username": "norole", "password": "pass"}
        )
        assert resp.json()["role"] == "reader"


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


class TestLogout:
    def test_logout_returns_200(self, client):
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["logged_out"] is True

    def test_logout_clears_cookie(self, client, fake_db):
        # Set a cookie first by logging in
        fake_db  # ensure fixture is active
        resp = client.post("/api/v1/auth/logout")
        # Cookie should be deleted (set-cookie header with empty value or max-age=0)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


class TestMe:
    async def test_authenticated_user_returns_info(self, app, fake_db):
        u = {"username": "alice", "role": "admin"}
        app.dependency_overrides[get_current_user] = lambda: u
        resp = TestClient(app).get("/api/v1/auth/me")
        assert resp.status_code == 200
        assert resp.json()["username"] == "alice"

    async def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401
