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

    async def test_sex_defaults_to_unknown_when_absent(self, client, fake_db):
        # Subjects from legacy data without a `sex` field should validate as
        # `unknown` — the field is required-with-default at the model layer.
        await fake_db["subjects"].insert_one({"subject_id": "S-002"})
        resp = client.get("/api/v1/subjects/S-002")
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject_id"] == "S-002"
        assert data["sex"] == "unknown"

    def test_returns_404_when_missing(self, client):
        resp = client.get("/api/v1/subjects/does-not-exist")
        assert resp.status_code == 404
        assert "does-not-exist" in resp.json()["detail"]

    async def test_resolves_by_objectid(self, client, fake_db):
        # Cases/samples carry the subject's ObjectId hex as their FK; the
        # endpoint must accept that form so the report can fetch in one hop.
        from bson import ObjectId

        oid = ObjectId()
        await fake_db["subjects"].insert_one(
            {"_id": oid, "subject_id": "S-003", "sex": "M"}
        )
        resp = client.get(f"/api/v1/subjects/{oid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject_id"] == "S-003"
        assert data["sex"] == "M"

    async def test_objectid_shaped_string_falls_back_to_subject_id(self, client, fake_db):
        # An ObjectId-shaped 24-hex string that isn't an actual subject _id
        # must still resolve when a subject_id field matches literally.
        hex_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
        await fake_db["subjects"].insert_one({"subject_id": hex_id, "sex": "X"})
        resp = client.get(f"/api/v1/subjects/{hex_id}")
        assert resp.status_code == 200
        assert resp.json()["subject_id"] == hex_id
