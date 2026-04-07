# tests/integration/test_subjects_router.py

import pytest
from bson import ObjectId
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.routers.subjects import router
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


async def insert_subject(db, subject_id="SUBJ001"):
    result = await db["subjects"].insert_one(
        {
            "subject_id": subject_id,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return result.inserted_id


async def insert_sample_for_subject(
    db, subject_oid, sample_id="SRR001", order_date="2026-01-01"
):
    result = await db["samples"].insert_one(
        {
            "subject_id": subject_oid,
            "case_id": ObjectId(),
            "sample_type": "sample",
            "material": "DNA",
            "sample": {"sample_id": sample_id},
            "run_id": ObjectId(),
            "order_date": order_date,
            "ingested_at": datetime.now(timezone.utc),
            "review": {"reviewed": False},
        }
    )
    return result.inserted_id


# ---------------------------------------------------------------------------
# GET /subjects
# ---------------------------------------------------------------------------


class TestListSubjects:
    async def test_empty_db_returns_empty_list(self, client, fake_db):
        resp = client.get("/api/v1/subjects")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_inserted_subjects(self, client, fake_db):
        await insert_subject(fake_db, "SUBJ001")
        await insert_subject(fake_db, "SUBJ002")
        resp = client.get("/api/v1/subjects")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    async def test_subject_ids_serialised_as_strings(self, client, fake_db):
        await insert_subject(fake_db, "SUBJ001")
        resp = client.get("/api/v1/subjects")
        data = resp.json()
        assert isinstance(data[0]["_id"], str)


# ---------------------------------------------------------------------------
# GET /subjects/{subject_id}/samples
# ---------------------------------------------------------------------------


class TestListSamplesForSubject:
    async def test_returns_samples_for_subject(self, client, fake_db):
        oid = await insert_subject(fake_db, "SUBJ001")
        await insert_sample_for_subject(fake_db, oid, "SRR001")
        resp = client.get("/api/v1/subjects/SUBJ001/samples")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["sample"]["sample_id"] == "SRR001"

    async def test_unknown_subject_returns_404(self, client, fake_db):
        resp = client.get("/api/v1/subjects/GHOST/samples")
        assert resp.status_code == 404

    async def test_returns_empty_list_when_no_samples(self, client, fake_db):
        await insert_subject(fake_db, "SUBJ001")
        resp = client.get("/api/v1/subjects/SUBJ001/samples")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_multiple_samples_returned(self, client, fake_db):
        oid = await insert_subject(fake_db, "SUBJ001")
        await insert_sample_for_subject(fake_db, oid, "SRR001", "2026-01-01")
        await insert_sample_for_subject(fake_db, oid, "SRR002", "2026-01-02")
        resp = client.get("/api/v1/subjects/SUBJ001/samples")
        assert len(resp.json()) == 2
