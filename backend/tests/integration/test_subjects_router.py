# tests/integration/test_subjects_router.py

import pytest
from fastapi.testclient import TestClient

from app.routers.subjects import router
from tests.helpers import make_test_app


@pytest.fixture
def app(fake_db, fake_blob):
    return make_test_app(router, fake_db, fake_blob)


@pytest.fixture
def client(app):
    return TestClient(app)


class TestGetSubject:
    async def test_returns_subject_when_found(self, client, fake_db):
        await fake_db["subjects"].insert_one({"subject_id": "S-001", "sex": "F"})
        resp = client.get("/api/v1/subjects/S-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject_id"] == "S-001"
        assert data["sex"] == "F"

    async def test_returns_subject_with_only_id(self, client, fake_db):
        # subjects upserted by ingest start out with only subject_id; sex stays null.
        await fake_db["subjects"].insert_one({"subject_id": "S-002"})
        resp = client.get("/api/v1/subjects/S-002")
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject_id"] == "S-002"
        assert data["sex"] is None

    async def test_returns_404_when_missing(self, client):
        resp = client.get("/api/v1/subjects/does-not-exist")
        assert resp.status_code == 404
        assert "does-not-exist" in resp.json()["detail"]
