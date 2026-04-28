# tests/unit/test_alerts_router.py
#
# Integration-style tests for the alerts router using FastAPI's TestClient
# with a mocked database. Uses dependency_overrides throughout — patch() does
# not work for FastAPI DI-resolved dependencies.
#
# Note: the router already has prefix="/alerts" internally, so we mount it
# at "/api/v1" to produce paths like /api/v1/alerts/ignorelist.

from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.routers import alerts
from app.routers.alerts import router as alerts_router
from app.auth.utils import get_current_user
from app.database import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_app():
    app = FastAPI()
    app.include_router(alerts_router, prefix="/api/v1")
    return app


def admin_user():
    return {"username": "testuser", "role": "admin"}


def override_auth(app, user):
    app.dependency_overrides[get_current_user] = lambda: user


# ---------------------------------------------------------------------------
# Ignorelist GET
# ---------------------------------------------------------------------------


class TestIgnorelistGet:
    def test_returns_empty_list(self):
        app = make_app()
        mock_db = MagicMock()
        mock_db[
            "outbreak_ignorelist"
        ].find.return_value.sort.return_value.to_list = AsyncMock(return_value=[])
        app.dependency_overrides[get_db] = lambda: mock_db
        override_auth(app, admin_user())

        resp = TestClient(app).get("/api/v1/alerts/ignorelist")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_serialised_docs(self):
        from bson import ObjectId

        app = make_app()
        doc = {
            "_id": ObjectId("64a1b2c3d4e5f6a7b8c9d0e1"),
            "taxon_id": 11676,
            "taxon_name": "Human immunodeficiency virus 1",
            "reason": None,
            "added_by": "admin",
            "added_at": "2024-03-15T10:00:00",
        }
        mock_db = MagicMock()
        mock_db[
            "outbreak_ignorelist"
        ].find.return_value.sort.return_value.to_list = AsyncMock(return_value=[doc])
        app.dependency_overrides[get_db] = lambda: mock_db
        override_auth(app, admin_user())

        resp = TestClient(app).get("/api/v1/alerts/ignorelist")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["taxon_id"] == 11676
        assert data[0]["_id"] == "64a1b2c3d4e5f6a7b8c9d0e1"


# ---------------------------------------------------------------------------
# Ignorelist POST
# ---------------------------------------------------------------------------


class TestIgnorelistPost:
    def _make_db(self, existing=None):
        from bson import ObjectId

        async def mock_insert_one(doc):
            doc["_id"] = ObjectId("64a1b2c3d4e5f6a7b8c9d0e1")
            return MagicMock(inserted_id=doc["_id"])

        mock_db = MagicMock()
        mock_db["outbreak_ignorelist"].find_one = AsyncMock(return_value=existing)
        mock_db["outbreak_ignorelist"].insert_one = mock_insert_one
        mock_db["meta"].update_one = AsyncMock()
        return mock_db

    def test_add_new_taxon_succeeds(self):
        app = make_app()
        app.dependency_overrides[get_db] = lambda: self._make_db(existing=None)
        override_auth(app, admin_user())

        resp = TestClient(app).post(
            "/api/v1/alerts/ignorelist",
            json={"taxon_id": 11676, "taxon_name": "HIV-1", "reason": "endemic"},
        )

        assert resp.status_code == 200
        assert resp.json()["taxon_id"] == 11676

    def test_duplicate_taxon_returns_409(self):
        app = make_app()
        app.dependency_overrides[get_db] = lambda: self._make_db(
            existing={"taxon_id": 11676}
        )
        override_auth(app, admin_user())

        resp = TestClient(app).post(
            "/api/v1/alerts/ignorelist", json={"taxon_id": 11676, "taxon_name": "HIV-1"}
        )

        assert resp.status_code == 409

    def test_add_clears_cache(self):
        alerts._cache[14] = {"outbreaks": []}
        app = make_app()
        app.dependency_overrides[get_db] = lambda: self._make_db(existing=None)
        override_auth(app, admin_user())

        TestClient(app).post(
            "/api/v1/alerts/ignorelist",
            json={"taxon_id": 99999, "taxon_name": "Test virus"},
        )

        assert alerts._cache == {}


# ---------------------------------------------------------------------------
# Ignorelist DELETE
# ---------------------------------------------------------------------------


class TestIgnorelistDelete:
    def test_delete_existing_taxon_succeeds(self):
        app = make_app()
        mock_db = MagicMock()
        mock_db["outbreak_ignorelist"].delete_one = AsyncMock(
            return_value=MagicMock(deleted_count=1)
        )
        mock_db["meta"].update_one = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_db
        override_auth(app, admin_user())

        resp = TestClient(app).delete("/api/v1/alerts/ignorelist/11676")

        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    def test_delete_nonexistent_taxon_returns_404(self):
        app = make_app()
        mock_db = MagicMock()
        mock_db["outbreak_ignorelist"].delete_one = AsyncMock(
            return_value=MagicMock(deleted_count=0)
        )
        mock_db["meta"].update_one = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_db
        override_auth(app, admin_user())

        resp = TestClient(app).delete("/api/v1/alerts/ignorelist/99999")

        assert resp.status_code == 404

    def test_delete_clears_cache(self):
        alerts._cache[14] = {"outbreaks": []}
        app = make_app()
        mock_db = MagicMock()
        mock_db["outbreak_ignorelist"].delete_one = AsyncMock(
            return_value=MagicMock(deleted_count=1)
        )
        mock_db["meta"].update_one = AsyncMock()
        app.dependency_overrides[get_db] = lambda: mock_db
        override_auth(app, admin_user())

        TestClient(app).delete("/api/v1/alerts/ignorelist/11676")

        assert alerts._cache == {}
