# tests/integration/test_users_router.py
#
# User identity is owned by Keycloak now; the only endpoints under /users are
# the per-user prefs/stats reads tied to the OIDC `sub`.

import pytest
from fastapi.testclient import TestClient

from app.routers.users import router
from tests.helpers import make_test_app


@pytest.fixture
def app(fake_db, fake_blob):
    return make_test_app(router, fake_db, fake_blob)


@pytest.fixture
def client(app):
    return TestClient(app)


# Matches the default user inserted by override_auth (sub-testuser, testuser).
DEFAULT_SUB = "sub-testuser"
DEFAULT_USERNAME = "testuser"


async def _insert_prefs(db, sub: str, username: str, prefs: dict | None = None):
    doc = {"sub": sub, "username": username}
    if prefs is not None:
        doc["preferences"] = prefs
    await db["users"].insert_one(doc)


async def _seed_reviews(db, username: str, count: int):
    for i in range(count):
        await db["cases"].insert_one(
            {
                "case_id": f"case_{username}_{i}",
                "review": {"reviewed": True, "reviewed_by": username},
            }
        )


# ---------------------------------------------------------------------------
# GET /users/me/stats
# ---------------------------------------------------------------------------


class TestMyStats:
    async def test_returns_stats_for_current_user(self, client, fake_db):
        await _seed_reviews(fake_db, DEFAULT_USERNAME, 5)
        resp = client.get("/api/v1/users/me/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == DEFAULT_USERNAME
        assert data["reviews"] == 5
        assert data["reviewer_title"] == "Novice"

    async def test_zero_reviews_returns_newbie(self, client, fake_db):
        resp = client.get("/api/v1/users/me/stats")
        data = resp.json()
        assert data["reviews"] == 0
        assert data["reviewer_title"] == "Newbie"


# ---------------------------------------------------------------------------
# GET /users/me/preferences
# ---------------------------------------------------------------------------


class TestGetMyPreferences:
    async def test_returns_default_when_no_preferences_saved(self, client, fake_db):
        await _insert_prefs(fake_db, DEFAULT_SUB, DEFAULT_USERNAME)
        resp = client.get("/api/v1/users/me/preferences")
        assert resp.status_code == 200
        assert resp.json()["preferred_kingdoms"] == ["Viruses"]

    async def test_returns_default_when_user_doc_missing(self, client, fake_db):
        resp = client.get("/api/v1/users/me/preferences")
        assert resp.status_code == 200
        assert resp.json()["preferred_kingdoms"] == ["Viruses"]

    async def test_returns_saved_preferences(self, client, fake_db):
        await _insert_prefs(
            fake_db,
            DEFAULT_SUB,
            DEFAULT_USERNAME,
            prefs={"preferred_kingdoms": ["Bacteria", "Eukaryota"]},
        )
        resp = client.get("/api/v1/users/me/preferences")
        assert resp.status_code == 200
        assert set(resp.json()["preferred_kingdoms"]) == {"Bacteria", "Eukaryota"}

    async def test_returns_empty_list_when_saved_as_empty(self, client, fake_db):
        await _insert_prefs(
            fake_db,
            DEFAULT_SUB,
            DEFAULT_USERNAME,
            prefs={"preferred_kingdoms": []},
        )
        resp = client.get("/api/v1/users/me/preferences")
        assert resp.status_code == 200
        assert resp.json()["preferred_kingdoms"] == []


# ---------------------------------------------------------------------------
# PATCH /users/me/preferences
# ---------------------------------------------------------------------------


class TestUpdateMyPreferences:
    async def test_saves_preferences(self, client, fake_db):
        resp = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_kingdoms": ["Bacteria", "Viruses"]},
        )
        assert resp.status_code == 200
        assert set(resp.json()["preferred_kingdoms"]) == {"Bacteria", "Viruses"}

    async def test_persists_to_database_keyed_by_sub(self, client, fake_db):
        client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_kingdoms": ["Archaea"]},
        )
        doc = await fake_db["users"].find_one({"sub": DEFAULT_SUB})
        assert doc is not None
        assert doc["preferences"]["preferred_kingdoms"] == ["Archaea"]
        assert doc["username"] == DEFAULT_USERNAME

    async def test_upserts_when_user_doc_missing(self, client, fake_db):
        # No pre-existing user doc; PATCH should create it.
        assert await fake_db["users"].find_one({"sub": DEFAULT_SUB}) is None
        resp = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_kingdoms": ["Bacteria"]},
        )
        assert resp.status_code == 200
        doc = await fake_db["users"].find_one({"sub": DEFAULT_SUB})
        assert doc["preferences"]["preferred_kingdoms"] == ["Bacteria"]

    async def test_allows_empty_list(self, client, fake_db):
        resp = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_kingdoms": []},
        )
        assert resp.status_code == 200
        assert resp.json()["preferred_kingdoms"] == []

    async def test_rejects_invalid_kingdom(self, client, fake_db):
        resp = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_kingdoms": ["Bacteria", "NotAKingdom"]},
        )
        assert resp.status_code == 422

    async def test_overwrites_existing_preferences(self, client, fake_db):
        await _insert_prefs(
            fake_db,
            DEFAULT_SUB,
            DEFAULT_USERNAME,
            prefs={"preferred_kingdoms": ["Viruses"]},
        )
        resp = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_kingdoms": ["Bacteria", "Eukaryota", "Archaea"]},
        )
        assert resp.status_code == 200
        assert set(resp.json()["preferred_kingdoms"]) == {
            "Bacteria",
            "Eukaryota",
            "Archaea",
        }
