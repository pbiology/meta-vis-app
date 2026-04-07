# tests/conftest.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
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


def user(role: str = "admin", username: str = "testuser") -> dict:
    return {"username": username, "role": role}


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
    import app.database as db_module
    from unittest.mock import patch

    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.dependency_overrides[get_db] = lambda: fake_db
    override_auth(application, role)

    # Patch at the source module — local imports inside handlers pick this up
    patch("app.database.get_blob_store", return_value=fake_blob).start()

    return application
