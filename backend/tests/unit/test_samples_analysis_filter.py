# tests/unit/test_samples_analysis_filter.py
#
# Covers the new ?analysis_type= filter on GET /api/v1/samples (Issue 28).

from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.utils import get_current_user
from app.database import get_db
from app.routers.samples import router as samples_router
from tests.helpers import insert_case as seed_case


def _make_app(fake_db):
    app = FastAPI()
    app.include_router(samples_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "alice",
        "role": "reader",
    }
    return app


async def _seed_samples(db):
    # The samples aggregation $lookups the producing analysis for live review
    # status, and the list shows latest analyses only.
    analysis_id = await seed_case(db, "CASE-1")
    await db["samples"].insert_many(
        [
            {
                "_id": ObjectId(),
                "analysis_id": analysis_id,
                "is_latest_analysis": True,
                "sample_id": "S-shotgun-1",
                "sample_type": "sample",
                "case_id": "CASE-1",
                "order_date": "2026-01-01",
                "taxprofiler": {"classifiers": {"kraken2": {"num_species": 10}}},
            },
            {
                "_id": ObjectId(),
                "analysis_id": analysis_id,
                "is_latest_analysis": True,
                "sample_id": "S-trana-1",
                "sample_type": "sample",
                "case_id": "CASE-1",
                "order_date": "2026-01-02",
                "trana": {"nanoplot_processed": {"number_of_reads": 123}},
            },
        ]
    )


class TestSamplesAnalysisFilter:
    async def test_no_filter_returns_all(self, fake_db):
        await _seed_samples(fake_db)
        client = TestClient(_make_app(fake_db))
        resp = client.get("/api/v1/samples")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    async def test_shotgun_returns_only_taxprofiler_samples(self, fake_db):
        await _seed_samples(fake_db)
        client = TestClient(_make_app(fake_db))
        resp = client.get("/api/v1/samples", params={"analysis_type": "shotgun"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["sample_id"] == "S-shotgun-1"

    async def test_amplicon_returns_only_trana_samples(self, fake_db):
        await _seed_samples(fake_db)
        client = TestClient(_make_app(fake_db))
        resp = client.get("/api/v1/samples", params={"analysis_type": "amplicon"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["sample_id"] == "S-trana-1"
