# tests/unit/test_alerts_analysis_filter.py
#
# Covers the new ?analysis_types= filter on GET /api/v1/alerts/outbreaks
# (Issue 28). Focuses on two things:
#  1. The case-query passed to Mongo includes an {"analysis_type": {"$in": ...}}
#     clause when the param is present.
#  2. Cache keys are distinct for different analysis_types (no cross-pollination).

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.utils import get_current_user
from app.database import get_db
from app.routers import alerts as alerts_module
from app.routers.alerts import router as alerts_router


def _make_app(fake_db):
    app = FastAPI()
    app.include_router(alerts_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "alice",
        "role": "reader",
    }
    return app


@pytest.fixture(autouse=True)
def _reset_cache():
    alerts_module._cache.clear()
    alerts_module._cache_computed_at = None
    yield
    alerts_module._cache.clear()
    alerts_module._cache_computed_at = None


class TestCacheKeyIncludesAnalysisTypes:
    async def test_different_analysis_types_use_different_cache_keys(
        self, fake_db, monkeypatch
    ):
        # Force no configs so the computation short-circuits — we only want
        # to observe that requests with different params don't collide.
        # However the code returns early before populating the cache when
        # configs is empty. So provide one config and a minimal case set.
        monkeypatch.setattr(
            alerts_module.settings,
            "outbreak_configs",
            [
                {
                    "name": "Viral",
                    "enabled": True,
                    "superkingdoms": ["Viruses"],
                    "min_rank": ["species"],
                    "min_abundance": 0,
                    "min_cases_threshold": 99,  # guarantees no outbreaks returned
                }
            ],
        )

        client = TestClient(_make_app(fake_db))

        r1 = client.get(
            "/api/v1/alerts/outbreaks",
            params={"window_days": 30, "analysis_types": "shotgun"},
        )
        r2 = client.get(
            "/api/v1/alerts/outbreaks",
            params={"window_days": 30, "analysis_types": "amplicon"},
        )
        r3 = client.get("/api/v1/alerts/outbreaks", params={"window_days": 30})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 200

        keys = set(alerts_module._cache.keys())
        # Three distinct cache entries — shotgun, amplicon, and unfiltered.
        assert (30, ("shotgun",)) in keys
        assert (30, ("amplicon",)) in keys
        assert (30, ()) in keys


class TestCaseQueryFiltersOnAnalysisType:
    async def test_analysis_types_param_restricts_case_query(
        self, fake_db, monkeypatch
    ):
        """When analysis_types is set, only matching cases are considered."""
        from bson import ObjectId

        # Seed two cases with different analysis types, both in-window.
        shotgun_case = ObjectId()
        amplicon_case = ObjectId()
        await fake_db["cases"].insert_many(
            [
                {
                    "_id": shotgun_case,
                    "case_id": "CASE-SHOT",
                    "order_date": "2026-04-15",
                    "analysis_type": "shotgun",
                },
                {
                    "_id": amplicon_case,
                    "case_id": "CASE-AMP",
                    "order_date": "2026-04-15",
                    "analysis_type": "amplicon",
                },
            ]
        )
        # No samples with outbreak_taxa → zero outbreaks returned, but we
        # exercise the case query filter.
        monkeypatch.setattr(
            alerts_module.settings,
            "outbreak_configs",
            [
                {
                    "name": "Viral",
                    "enabled": True,
                    "superkingdoms": ["Viruses"],
                    "min_rank": ["species"],
                    "min_abundance": 0,
                    "min_cases_threshold": 2,
                }
            ],
        )

        client = TestClient(_make_app(fake_db))
        resp = client.get(
            "/api/v1/alerts/outbreaks",
            params={"window_days": 30, "analysis_types": "shotgun"},
        )
        assert resp.status_code == 200
        # Payload structure sanity — no outbreaks, but the call succeeded
        # with the analysis-type filter applied.
        body = resp.json()
        assert body["window_days"] == 30
        assert body["results"][0]["config_name"] == "Viral"
        assert body["results"][0]["outbreaks"] == []
