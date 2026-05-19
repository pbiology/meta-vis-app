# tests/unit/test_users_preferences.py
#
# Tests for the /users/me/preferences endpoints, focused on the
# visible_analysis_types field (Issue 28). Identity comes from the OIDC `sub`.

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.utils import get_current_user
from app.database import get_db
from app.routers.users import router as users_router


SUB = "sub-alice"
USERNAME = "alice"


def _make_app(fake_db):
    app = FastAPI()
    app.include_router(users_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": SUB,
        "username": USERNAME,
        "role": "reader",
    }
    return app


@pytest.fixture
async def seeded_db(fake_db):
    await fake_db["users"].insert_one({"sub": SUB, "username": USERNAME})
    return fake_db


class TestGetMyPreferences:
    async def test_returns_defaults_when_user_has_no_prefs_doc(self, seeded_db):
        client = TestClient(_make_app(seeded_db))
        resp = client.get("/api/v1/users/me/preferences")
        assert resp.status_code == 200
        body = resp.json()
        assert body["preferred_kingdoms"] == ["Viruses"]
        assert sorted(body["visible_analysis_types"]) == ["amplicon", "shotgun"]

    async def test_returns_defaults_when_user_missing(self, fake_db):
        client = TestClient(_make_app(fake_db))
        resp = client.get("/api/v1/users/me/preferences")
        assert resp.status_code == 200
        body = resp.json()
        assert sorted(body["visible_analysis_types"]) == ["amplicon", "shotgun"]


class TestPatchMyPreferences:
    async def test_round_trip_persists_both_fields(self, seeded_db):
        client = TestClient(_make_app(seeded_db))

        patch_body = {
            "preferred_kingdoms": ["Bacteria", "Viruses"],
            "visible_analysis_types": ["amplicon"],
        }
        patch_resp = client.patch("/api/v1/users/me/preferences", json=patch_body)
        assert patch_resp.status_code == 200
        assert patch_resp.json() == patch_body

        get_resp = client.get("/api/v1/users/me/preferences")
        assert get_resp.status_code == 200
        assert get_resp.json() == patch_body

    async def test_rejects_unknown_analysis_type(self, seeded_db):
        client = TestClient(_make_app(seeded_db))
        resp = client.patch(
            "/api/v1/users/me/preferences",
            json={
                "preferred_kingdoms": ["Viruses"],
                "visible_analysis_types": ["bogus"],
            },
        )
        assert resp.status_code == 422

    async def test_rejects_empty_analysis_types(self, seeded_db):
        client = TestClient(_make_app(seeded_db))
        resp = client.patch(
            "/api/v1/users/me/preferences",
            json={
                "preferred_kingdoms": ["Viruses"],
                "visible_analysis_types": [],
            },
        )
        assert resp.status_code == 422
