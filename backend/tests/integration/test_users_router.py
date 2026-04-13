# tests/integration/test_users_router.py

import pytest
from fastapi.testclient import TestClient

from app.routers.users import router
from app.auth.utils import hash_password
from tests.helpers import make_test_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app(fake_db, fake_blob):
    return make_test_app(router, fake_db, fake_blob)


@pytest.fixture
def client(app):
    return TestClient(app)


async def insert_user(db, username="alice", role="reader", reviews=0):
    await db["users"].insert_one(
        {
            "username": username,
            "password_hash": hash_password("secret"),
            "role": role,
        }
    )
    # Insert reviewed cases to simulate review count
    for i in range(reviews):
        await db["cases"].insert_one(
            {
                "case_id": f"case_{username}_{i}",
                "review": {"reviewed": True, "reviewed_by": username},
            }
        )


# ---------------------------------------------------------------------------
# GET /users
# ---------------------------------------------------------------------------


class TestListUsers:
    async def test_empty_db_returns_empty_list(self, client, fake_db):
        resp = client.get("/api/v1/users")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_users(self, client, fake_db):
        await insert_user(fake_db, "alice", "reader")
        resp = client.get("/api/v1/users")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["username"] == "alice"
        assert data[0]["role"] == "reader"

    async def test_password_hash_not_exposed(self, client, fake_db):
        await insert_user(fake_db, "alice")
        resp = client.get("/api/v1/users")
        assert "password_hash" not in resp.json()[0]

    async def test_review_count_correct(self, client, fake_db):
        await insert_user(fake_db, "alice", reviews=3)
        resp = client.get("/api/v1/users")
        assert resp.json()[0]["reviews"] == 3

    async def test_reviewer_title_included(self, client, fake_db):
        await insert_user(fake_db, "alice", reviews=0)
        resp = client.get("/api/v1/users")
        assert resp.json()[0]["reviewer_title"] == "Newbie"


# ---------------------------------------------------------------------------
# GET /users/me/stats
# ---------------------------------------------------------------------------


class TestMyStats:
    async def test_returns_stats_for_current_user(self, client, fake_db):
        await insert_user(fake_db, "testuser", reviews=5)
        resp = client.get("/api/v1/users/me/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        assert data["reviews"] == 5
        assert data["reviewer_title"] == "Novice"

    async def test_zero_reviews_returns_newbie(self, client, fake_db):
        resp = client.get("/api/v1/users/me/stats")
        data = resp.json()
        assert data["reviews"] == 0
        assert data["reviewer_title"] == "Newbie"


# ---------------------------------------------------------------------------
# POST /users
# ---------------------------------------------------------------------------


class TestCreateUser:
    async def test_creates_user_successfully(self, client, fake_db):
        resp = client.post(
            "/api/v1/users",
            json={"username": "bob", "password": "pass123", "role": "writer"},
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "bob"
        assert resp.json()["role"] == "writer"

    async def test_duplicate_username_returns_409(self, client, fake_db):
        await insert_user(fake_db, "bob")
        resp = client.post(
            "/api/v1/users", json={"username": "bob", "password": "pass123"}
        )
        assert resp.status_code == 409

    async def test_invalid_role_returns_422(self, client, fake_db):
        resp = client.post(
            "/api/v1/users",
            json={"username": "bob", "password": "pass123", "role": "superuser"},
        )
        assert resp.status_code == 422

    async def test_default_role_is_reader(self, client, fake_db):
        resp = client.post(
            "/api/v1/users", json={"username": "bob", "password": "pass123"}
        )
        assert resp.json()["role"] == "reader"


# ---------------------------------------------------------------------------
# PATCH /users/{username}/role
# ---------------------------------------------------------------------------


class TestUpdateRole:
    async def test_updates_role_successfully(self, client, fake_db):
        await insert_user(fake_db, "alice", "reader")
        resp = client.patch("/api/v1/users/alice/role", json={"role": "writer"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "writer"

    async def test_unknown_user_returns_404(self, client, fake_db):
        resp = client.patch("/api/v1/users/ghost/role", json={"role": "writer"})
        assert resp.status_code == 404

    async def test_invalid_role_returns_422(self, client, fake_db):
        await insert_user(fake_db, "alice")
        resp = client.patch("/api/v1/users/alice/role", json={"role": "superuser"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /users/{username}/password
# ---------------------------------------------------------------------------


class TestUpdatePassword:
    async def test_updates_password_successfully(self, client, fake_db):
        await insert_user(fake_db, "alice")
        resp = client.patch(
            "/api/v1/users/alice/password", json={"password": "newpass"}
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] is True

    async def test_unknown_user_returns_404(self, client, fake_db):
        resp = client.patch(
            "/api/v1/users/ghost/password", json={"password": "newpass"}
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /users/{username}
# ---------------------------------------------------------------------------


class TestDeleteUser:
    async def test_deletes_user_successfully(self, client, fake_db):
        await insert_user(fake_db, "alice")
        resp = client.delete("/api/v1/users/alice")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    async def test_unknown_user_returns_404(self, client, fake_db):
        resp = client.delete("/api/v1/users/ghost")
        assert resp.status_code == 404

    async def test_cannot_delete_own_account(self, client, fake_db):
        # testuser is the authenticated user set by override_auth in make_test_app
        await insert_user(fake_db, "testuser")
        resp = client.delete("/api/v1/users/testuser")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /users/me/preferences
# ---------------------------------------------------------------------------


class TestGetMyPreferences:
    async def test_returns_default_when_no_preferences_saved(self, client, fake_db):
        # Insert the authenticated user with no preferences field
        await insert_user(fake_db, "testuser")
        resp = client.get("/api/v1/users/me/preferences")
        assert resp.status_code == 200
        assert resp.json()["preferred_kingdoms"] == ["Viruses"]

    async def test_returns_saved_preferences(self, client, fake_db):
        await fake_db["users"].insert_one(
            {
                "username": "testuser",
                "password_hash": "x",
                "role": "reader",
                "preferences": {"preferred_kingdoms": ["Bacteria", "Eukaryota"]},
            }
        )
        resp = client.get("/api/v1/users/me/preferences")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data["preferred_kingdoms"]) == {"Bacteria", "Eukaryota"}

    async def test_returns_empty_list_when_saved_as_empty(self, client, fake_db):
        await fake_db["users"].insert_one(
            {
                "username": "testuser",
                "password_hash": "x",
                "role": "reader",
                "preferences": {"preferred_kingdoms": []},
            }
        )
        resp = client.get("/api/v1/users/me/preferences")
        assert resp.status_code == 200
        assert resp.json()["preferred_kingdoms"] == []


# ---------------------------------------------------------------------------
# PATCH /users/me/preferences
# ---------------------------------------------------------------------------


class TestUpdateMyPreferences:
    async def test_saves_preferences(self, client, fake_db):
        await insert_user(fake_db, "testuser")
        resp = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_kingdoms": ["Bacteria", "Viruses"]},
        )
        assert resp.status_code == 200
        assert set(resp.json()["preferred_kingdoms"]) == {"Bacteria", "Viruses"}

    async def test_persists_to_database(self, client, fake_db):
        await insert_user(fake_db, "testuser")
        client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_kingdoms": ["Archaea"]},
        )
        doc = await fake_db["users"].find_one({"username": "testuser"})
        assert doc["preferences"]["preferred_kingdoms"] == ["Archaea"]

    async def test_allows_empty_list(self, client, fake_db):
        await insert_user(fake_db, "testuser")
        resp = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_kingdoms": []},
        )
        assert resp.status_code == 200
        assert resp.json()["preferred_kingdoms"] == []

    async def test_rejects_invalid_kingdom(self, client, fake_db):
        await insert_user(fake_db, "testuser")
        resp = client.patch(
            "/api/v1/users/me/preferences",
            json={"preferred_kingdoms": ["Bacteria", "NotAKingdom"]},
        )
        assert resp.status_code == 422

    async def test_overwrites_existing_preferences(self, client, fake_db):
        await fake_db["users"].insert_one(
            {
                "username": "testuser",
                "password_hash": "x",
                "role": "reader",
                "preferences": {"preferred_kingdoms": ["Viruses"]},
            }
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
