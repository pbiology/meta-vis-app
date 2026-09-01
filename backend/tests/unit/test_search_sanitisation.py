# tests/unit/test_search_sanitisation.py
#
# Covers ToDo #101: user-supplied `search` is escaped before being passed to
# MongoDB `$regex`, and the param length is capped to prevent ReDoS.

import time

from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.utils import get_current_user
from app.database import get_db
from app.routers.cases import router as cases_router
from tests.helpers import insert_case as seed_case
from app.routers.samples import router as samples_router


def _make_app(router, fake_db):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: {
        "username": "alice",
        "role": "reader",
    }
    return app


PATHOLOGICAL = ".*.*.*(.+)+.*"


class TestCasesSearchSanitisation:
    async def test_pathological_regex_is_escaped(self, fake_db):
        await seed_case(fake_db, "CASE-1")
        client = TestClient(_make_app(cases_router, fake_db))
        start = time.perf_counter()
        resp = client.get("/api/v1/cases", params={"search": PATHOLOGICAL})
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        # Escaped pattern is a literal substring search — no match expected.
        assert resp.json()["total"] == 0
        assert elapsed < 0.5

    async def test_literal_match_still_works(self, fake_db):
        await seed_case(fake_db, "CASE-foo")
        await seed_case(fake_db, "CASE-bar")
        client = TestClient(_make_app(cases_router, fake_db))
        resp = client.get("/api/v1/cases", params={"search": "foo"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["case"]["case_id"] == "CASE-foo"

    def test_search_length_capped(self, fake_db):
        client = TestClient(_make_app(cases_router, fake_db))
        resp = client.get("/api/v1/cases", params={"search": "a" * 200})
        assert resp.status_code == 422


class TestSamplesSearchSanitisation:
    async def test_pathological_regex_is_escaped(self, fake_db):
        await fake_db["samples"].insert_one(
            {
                "_id": ObjectId(),
                "sample_id": "S-1",
                "sample_type": "sample",
                "case_id": "CASE-1",
            }
        )
        await seed_case(fake_db, "CASE-1")
        client = TestClient(_make_app(samples_router, fake_db))
        start = time.perf_counter()
        resp = client.get("/api/v1/samples", params={"search": PATHOLOGICAL})
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert elapsed < 0.5

    def test_search_length_capped(self, fake_db):
        client = TestClient(_make_app(samples_router, fake_db))
        resp = client.get("/api/v1/samples", params={"search": "a" * 200})
        assert resp.status_code == 422
