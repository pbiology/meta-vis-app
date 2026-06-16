# tests/conftest.py

# app.config builds a module-level Settings() on import, and the required
# fields (Mongo host/db, Keycloak issuer, CORS) have no defaults — by design,
# so a misconfigured deploy fails fast. Tests use mongomock and never open a
# real connection, so set harmless placeholders here, before importing app.*.
# This keeps the suite self-contained: it does not depend on .env files, CWD,
# or a CI `env:` block. setdefault means an explicit env override still wins.
import os

os.environ.setdefault("MONGODB_HOST", "localhost")
os.environ.setdefault("MONGODB_DB_NAME", "test")
os.environ.setdefault("KEYCLOAK_ISSUER", "http://localhost:8081/realms/test")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

import pytest
from fastapi import FastAPI
from mongomock_motor import AsyncMongoMockClient

from app.database import get_db
from app.auth.utils import get_current_user, require_role


# ---------------------------------------------------------------------------
# In-memory MongoDB — reset per test
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_db():
    client = AsyncMongoMockClient()
    return client["test_db"]


# ---------------------------------------------------------------------------
# Blob store mock — simple dict backend
# ---------------------------------------------------------------------------


class FakeBlobStore:
    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def put(self, key: str, value: str):
        self._store[key] = value

    async def delete_prefix(self, prefix: str):
        keys = [k for k in self._store if k.startswith(prefix)]
        for k in keys:
            del self._store[k]


@pytest.fixture
def fake_blob():
    return FakeBlobStore()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def user(
    role: str = "admin",
    username: str = "testuser",
    sub: str | None = None,
) -> dict:
    return {"sub": sub or f"sub-{username}", "username": username, "role": role}


def override_auth(app: FastAPI, role: str = "admin", username: str = "testuser"):
    u = user(role, username)
    app.dependency_overrides[get_current_user] = lambda: u
    for r in ("reader", "writer", "admin"):
        app.dependency_overrides[require_role(r)] = lambda u=u: u
    # FastAPI caches require_role instances per args, so override all combos
    app.dependency_overrides[require_role("writer", "admin")] = lambda u=u: u


# ---------------------------------------------------------------------------
# Standard app factory
# ---------------------------------------------------------------------------


def make_test_app(router, fake_db, fake_blob, role: str = "admin"):
    """Build a minimal FastAPI test app with the given router and mocked deps."""
    from unittest.mock import patch

    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.dependency_overrides[get_db] = lambda: fake_db
    override_auth(application, role)

    # Patch at the source module — local imports inside handlers pick this up
    patch("app.database.get_blob_store", return_value=fake_blob).start()

    return application
