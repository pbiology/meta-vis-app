# tests/helpers.py
# Importable test helpers — shared across integration test files.
# (conftest.py cannot be imported directly as a module.)

from unittest.mock import patch
from fastapi import FastAPI

from app.database import get_db
from app.auth.utils import get_current_user, require_role


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


def make_user(role: str = "admin", username: str = "testuser") -> dict:
    return {"username": username, "role": role}


def override_auth(app: FastAPI, role: str = "admin", username: str = "testuser"):
    u = make_user(role, username)
    app.dependency_overrides[get_current_user] = lambda: u
    for r in ("reader", "writer", "admin"):
        app.dependency_overrides[require_role(r)] = lambda u=u: u
    app.dependency_overrides[require_role("writer", "admin")] = lambda u=u: u


def make_test_app(router, fake_db, fake_blob, role: str = "admin"):
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.dependency_overrides[get_db] = lambda: fake_db
    override_auth(application, role)
    patch("app.database.get_blob_store", return_value=fake_blob).start()
    return application
