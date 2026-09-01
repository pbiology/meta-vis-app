# tests/integration/test_subjects_router.py

import pytest
from fastapi.testclient import TestClient

from app.routers.subjects import router
from tests.helpers import insert_case as seed_case
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

    async def test_objectid_shaped_string_falls_back_to_subject_id(
        self, client, fake_db
    ):
        # An ObjectId-shaped 24-hex string that isn't an actual subject _id
        # must still resolve when a subject_id field matches literally.
        hex_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
        await fake_db["subjects"].insert_one({"subject_id": hex_id, "sex": "X"})
        resp = client.get(f"/api/v1/subjects/{hex_id}")
        assert resp.status_code == 200
        assert resp.json()["subject_id"] == hex_id


class TestListSubjects:
    def test_empty_list(self, client):
        resp = client.get("/api/v1/subjects")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"total": 0, "page": 1, "pages": 1, "items": []}

    async def test_counts_split_by_analysis_type(self, client, fake_db):
        from bson import ObjectId

        oid = ObjectId()
        await fake_db["subjects"].insert_one(
            {"_id": oid, "subject_id": "S-001", "sex": "F"}
        )
        # analysis_type lives on the analysis, so counts walk cases -> analyses.
        await seed_case(fake_db, "C1", subject_id=oid, analysis_type="shotgun")
        await seed_case(fake_db, "C2", subject_id=oid, analysis_type="shotgun")
        await seed_case(fake_db, "C3", subject_id=oid, analysis_type="amplicon")
        resp = client.get("/api/v1/subjects")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        item = items[0]
        assert item["subject_id"] == "S-001"
        assert item["sex"] == "F"
        assert item["shotgun_count"] == 2
        assert item["amplicon_count"] == 1

    async def test_subject_without_cases_shows_zero_counts(self, client, fake_db):
        await fake_db["subjects"].insert_one({"subject_id": "S-002", "sex": "M"})
        resp = client.get("/api/v1/subjects")
        item = resp.json()["items"][0]
        assert item["shotgun_count"] == 0
        assert item["amplicon_count"] == 0

    async def test_search_filters_by_subject_id(self, client, fake_db):
        await fake_db["subjects"].insert_many(
            [
                {"subject_id": "ALPHA-1"},
                {"subject_id": "BETA-2"},
            ]
        )
        resp = client.get("/api/v1/subjects", params={"search": "alpha"})
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["subject_id"] == "ALPHA-1"

    async def test_pagination_totals(self, client, fake_db):
        await fake_db["subjects"].insert_many(
            [{"subject_id": f"S-{i:03d}"} for i in range(120)]
        )
        resp = client.get("/api/v1/subjects")
        data = resp.json()
        assert data["total"] == 120
        assert data["pages"] == 3
        assert len(data["items"]) == 50


class TestSubjectCases:
    async def test_returns_subject_cases_with_stats(self, client, fake_db):
        from bson import ObjectId

        oid = ObjectId()
        await fake_db["subjects"].insert_one({"_id": oid, "subject_id": "S-001"})
        await seed_case(
            fake_db, "C1", subject_id=oid, analysis_type="shotgun", sample_count=3
        )
        await seed_case(fake_db, "C2", subject_id=oid, analysis_type="amplicon")
        resp = client.get("/api/v1/subjects/S-001/cases")
        assert resp.status_code == 200
        rows = resp.json()
        assert {r["case"]["case_id"] for r in rows} == {"C1", "C2"}
        c1 = next(r for r in rows if r["case"]["case_id"] == "C1")
        assert c1["latest"]["sample_count"] == 3
        assert c1["case"]["subject_id"] == str(oid)

    async def test_resolves_by_objectid(self, client, fake_db):
        from bson import ObjectId

        oid = ObjectId()
        await fake_db["subjects"].insert_one({"_id": oid, "subject_id": "S-002"})
        await seed_case(fake_db, "C1", subject_id=oid, analysis_type="shotgun")
        resp = client.get(f"/api/v1/subjects/{oid}/cases")
        assert resp.status_code == 200
        assert [r["case"]["case_id"] for r in resp.json()] == ["C1"]

    async def test_subject_with_no_cases_returns_empty(self, client, fake_db):
        await fake_db["subjects"].insert_one({"subject_id": "S-003"})
        resp = client.get("/api/v1/subjects/S-003/cases")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_404_for_unknown_subject(self, client):
        resp = client.get("/api/v1/subjects/nope/cases")
        assert resp.status_code == 404
        assert "nope" in resp.json()["detail"]
