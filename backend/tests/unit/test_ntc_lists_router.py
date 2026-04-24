# tests/unit/test_ntc_lists_router.py
#
# Tests for the NTC ignorelist and known contaminants CRUD endpoints,
# plus the contaminant-alerts endpoint.

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from mongomock_motor import AsyncMongoMockClient

from app.routers.ntc import (
    router as ntc_router,
    invalidate_contaminant_cache,
    invalidate_ntc_trends_cache,
)
from app.database import get_db
from app.auth.utils import get_current_user, require_role


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_trends_cache():
    invalidate_ntc_trends_cache()


@pytest.fixture
def fake_db():
    client = AsyncMongoMockClient()
    return client["test_db"]


def make_app(fake_db, role: str = "admin"):
    app = FastAPI()
    app.include_router(ntc_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: fake_db
    u = {"username": "testuser", "role": role}
    app.dependency_overrides[get_current_user] = lambda: u
    app.dependency_overrides[require_role("writer", "admin")] = lambda: u
    app.dependency_overrides[require_role("admin")] = lambda: u
    return app


def make_ntc_doc(
    sample_id: str,
    case_id: str,
    order_date: str,
    profile: list[dict] | None = None,
) -> dict:
    doc: dict = {
        "sample_id": sample_id,
        "case_id": case_id,
        "sample_type": "negative_ctrl",
        "material": "DNA",
        "order_date": order_date,
        "profiles": [],
        "taxprofiler": {},
    }
    if profile is not None:
        doc["profiles"] = [{"classifier": "kraken2", "profile": profile}]
    return doc


def make_taxon(
    taxon_id: int, name: str, abundance: float, superkingdom: str = "Bacteria"
) -> dict:
    return {
        "taxon_id": taxon_id,
        "name": name,
        "abundance": abundance,
        "superkingdom": superkingdom,
        "rank": "species",
    }


# ---------------------------------------------------------------------------
# NTC ignorelist — GET
# ---------------------------------------------------------------------------


class TestNtcIgnorelistGet:
    async def test_returns_empty_list_when_no_entries(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/ignorelist")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_existing_entries(self, fake_db):
        await fake_db["ntc_ignorelist"].insert_one(
            {
                "taxon_id": 1743,
                "taxon_name": "Cutibacterium acnes",
                "superkingdom": "Bacteria",
                "reason": None,
                "added_by": "alice",
                "added_at": "2026-01-01T00:00:00",
            }
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/ignorelist")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["taxon_id"] == 1743
        assert "_id" in data[0]


# ---------------------------------------------------------------------------
# NTC ignorelist — POST
# ---------------------------------------------------------------------------


class TestNtcIgnorelistPost:
    async def test_add_new_taxon_succeeds(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).post(
            "/api/v1/ntc/ignorelist",
            json={
                "taxon_id": 1743,
                "taxon_name": "Cutibacterium acnes",
                "superkingdom": "Bacteria",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["taxon_id"] == 1743
        assert data["added_by"] == "testuser"

    async def test_duplicate_taxon_returns_409(self, fake_db):
        await fake_db["ntc_ignorelist"].insert_one(
            {"taxon_id": 1743, "taxon_name": "x"}
        )
        app = make_app(fake_db)
        resp = TestClient(app).post(
            "/api/v1/ntc/ignorelist",
            json={
                "taxon_id": 1743,
                "taxon_name": "Cutibacterium acnes",
            },
        )
        assert resp.status_code == 409

    async def test_reader_cannot_add(self, fake_db):
        app = make_app(fake_db, role="reader")
        # Remove the writer/admin override to test real role enforcement
        from app.auth.utils import require_role as rr

        app.dependency_overrides.pop(rr("writer", "admin"), None)
        resp = TestClient(app).post(
            "/api/v1/ntc/ignorelist",
            json={
                "taxon_id": 9999,
                "taxon_name": "Test taxon",
            },
        )
        assert resp.status_code in (401, 403)

    async def test_add_invalidates_contaminant_cache(self, fake_db):
        import app.routers.ntc as ntc_module

        ntc_module._contaminant_alert_cache = {
            90: {"alerts": [], "contaminant_case_ids": []}
        }
        app_ = make_app(fake_db)
        TestClient(app_).post(
            "/api/v1/ntc/ignorelist",
            json={
                "taxon_id": 1743,
                "taxon_name": "Cutibacterium acnes",
            },
        )
        assert ntc_module._contaminant_alert_cache == {}

    async def test_cannot_add_to_ignorelist_if_on_contaminants(self, fake_db):
        await fake_db["ntc_known_contaminants"].insert_one(
            {
                "taxon_id": 1743,
                "taxon_name": "Cutibacterium acnes",
                "min_reads": 3,
            }
        )
        app = make_app(fake_db)
        resp = TestClient(app).post(
            "/api/v1/ntc/ignorelist",
            json={
                "taxon_id": 1743,
                "taxon_name": "Cutibacterium acnes",
            },
        )
        assert resp.status_code == 409
        assert "known contaminants" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# NTC ignorelist — PATCH
# ---------------------------------------------------------------------------


class TestNtcIgnorelistPatch:
    async def test_update_reason_succeeds(self, fake_db):
        await fake_db["ntc_ignorelist"].insert_one(
            {"taxon_id": 1743, "taxon_name": "x", "reason": None}
        )
        app = make_app(fake_db)
        resp = TestClient(app).patch(
            "/api/v1/ntc/ignorelist/1743", json={"reason": "Skin flora"}
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] is True

    async def test_update_nonexistent_taxon_returns_404(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).patch(
            "/api/v1/ntc/ignorelist/99999", json={"reason": "x"}
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# NTC ignorelist — DELETE
# ---------------------------------------------------------------------------


class TestNtcIgnorelistDelete:
    async def test_delete_existing_taxon_succeeds(self, fake_db):
        await fake_db["ntc_ignorelist"].insert_one(
            {"taxon_id": 1743, "taxon_name": "x"}
        )
        app = make_app(fake_db)
        resp = TestClient(app).delete("/api/v1/ntc/ignorelist/1743")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    async def test_delete_nonexistent_taxon_returns_404(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).delete("/api/v1/ntc/ignorelist/99999")
        assert resp.status_code == 404

    async def test_delete_invalidates_contaminant_cache(self, fake_db):
        import app.routers.ntc as ntc_module

        await fake_db["ntc_ignorelist"].insert_one(
            {"taxon_id": 1743, "taxon_name": "x"}
        )
        ntc_module._contaminant_alert_cache = {
            90: {"alerts": [], "contaminant_case_ids": []}
        }
        app_ = make_app(fake_db)
        TestClient(app_).delete("/api/v1/ntc/ignorelist/1743")
        assert ntc_module._contaminant_alert_cache == {}


# ---------------------------------------------------------------------------
# NTC known contaminants — GET
# ---------------------------------------------------------------------------


class TestNtcContaminantsGet:
    async def test_returns_empty_list_when_no_entries(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/contaminants")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_existing_entries(self, fake_db):
        await fake_db["ntc_known_contaminants"].insert_one(
            {
                "taxon_id": 329,
                "taxon_name": "Ralstonia pickettii",
                "superkingdom": "Bacteria",
                "min_reads": 5,
                "notes": None,
                "added_by": "alice",
                "added_at": "2026-01-01T00:00:00",
            }
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/contaminants")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["taxon_id"] == 329
        assert data[0]["min_reads"] == 5


# ---------------------------------------------------------------------------
# NTC known contaminants — POST
# ---------------------------------------------------------------------------


class TestNtcContaminantsPost:
    async def test_add_new_contaminant_succeeds(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).post(
            "/api/v1/ntc/contaminants",
            json={
                "taxon_id": 329,
                "taxon_name": "Ralstonia pickettii",
                "superkingdom": "Bacteria",
                "min_reads": 5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["taxon_id"] == 329
        assert data["min_reads"] == 5
        assert data["added_by"] == "testuser"

    async def test_default_min_reads_is_3(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).post(
            "/api/v1/ntc/contaminants",
            json={
                "taxon_id": 329,
                "taxon_name": "Ralstonia pickettii",
            },
        )
        assert resp.json()["min_reads"] == 3

    async def test_duplicate_taxon_returns_409(self, fake_db):
        await fake_db["ntc_known_contaminants"].insert_one(
            {
                "taxon_id": 329,
                "taxon_name": "x",
                "min_reads": 3,
            }
        )
        app = make_app(fake_db)
        resp = TestClient(app).post(
            "/api/v1/ntc/contaminants",
            json={
                "taxon_id": 329,
                "taxon_name": "Ralstonia pickettii",
            },
        )
        assert resp.status_code == 409

    async def test_add_invalidates_contaminant_cache(self, fake_db):
        import app.routers.ntc as ntc_module

        ntc_module._contaminant_alert_cache = {
            90: {"alerts": [], "contaminant_case_ids": []}
        }
        app_ = make_app(fake_db)
        TestClient(app_).post(
            "/api/v1/ntc/contaminants",
            json={
                "taxon_id": 329,
                "taxon_name": "Ralstonia pickettii",
            },
        )
        assert ntc_module._contaminant_alert_cache == {}

    async def test_cannot_add_to_contaminants_if_on_ignorelist(self, fake_db):
        await fake_db["ntc_ignorelist"].insert_one(
            {
                "taxon_id": 1743,
                "taxon_name": "Cutibacterium acnes",
            }
        )
        app = make_app(fake_db)
        resp = TestClient(app).post(
            "/api/v1/ntc/contaminants",
            json={
                "taxon_id": 1743,
                "taxon_name": "Cutibacterium acnes",
            },
        )
        assert resp.status_code == 409
        assert "ignorelist" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# NTC known contaminants — PATCH
# ---------------------------------------------------------------------------


class TestNtcContaminantsPatch:
    async def test_update_min_reads_succeeds(self, fake_db):
        await fake_db["ntc_known_contaminants"].insert_one(
            {
                "taxon_id": 329,
                "taxon_name": "x",
                "min_reads": 3,
                "notes": None,
            }
        )
        app = make_app(fake_db)
        resp = TestClient(app).patch(
            "/api/v1/ntc/contaminants/329", json={"min_reads": 10}
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] is True

    async def test_update_notes_succeeds(self, fake_db):
        await fake_db["ntc_known_contaminants"].insert_one(
            {
                "taxon_id": 329,
                "taxon_name": "x",
                "min_reads": 3,
                "notes": None,
            }
        )
        app = make_app(fake_db)
        resp = TestClient(app).patch(
            "/api/v1/ntc/contaminants/329", json={"notes": "Water contaminant"}
        )
        assert resp.status_code == 200

    async def test_empty_patch_body_returns_422(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).patch("/api/v1/ntc/contaminants/329", json={})
        assert resp.status_code == 422

    async def test_update_nonexistent_taxon_returns_404(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).patch(
            "/api/v1/ntc/contaminants/99999", json={"min_reads": 5}
        )
        assert resp.status_code == 404

    async def test_patch_invalidates_contaminant_cache(self, fake_db):
        import app.routers.ntc as ntc_module

        await fake_db["ntc_known_contaminants"].insert_one(
            {
                "taxon_id": 329,
                "taxon_name": "x",
                "min_reads": 3,
                "notes": None,
            }
        )
        ntc_module._contaminant_alert_cache = {
            90: {"alerts": [], "contaminant_case_ids": []}
        }
        app_ = make_app(fake_db)
        TestClient(app_).patch("/api/v1/ntc/contaminants/329", json={"min_reads": 10})
        assert ntc_module._contaminant_alert_cache == {}


# ---------------------------------------------------------------------------
# NTC known contaminants — DELETE
# ---------------------------------------------------------------------------


class TestNtcContaminantsDelete:
    async def test_delete_existing_contaminant_succeeds(self, fake_db):
        await fake_db["ntc_known_contaminants"].insert_one(
            {
                "taxon_id": 329,
                "taxon_name": "x",
                "min_reads": 3,
            }
        )
        app = make_app(fake_db)
        resp = TestClient(app).delete("/api/v1/ntc/contaminants/329")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    async def test_delete_nonexistent_contaminant_returns_404(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).delete("/api/v1/ntc/contaminants/99999")
        assert resp.status_code == 404

    async def test_delete_invalidates_contaminant_cache(self, fake_db):
        import app.routers.ntc as ntc_module

        await fake_db["ntc_known_contaminants"].insert_one(
            {
                "taxon_id": 329,
                "taxon_name": "x",
                "min_reads": 3,
            }
        )
        ntc_module._contaminant_alert_cache = {
            90: {"alerts": [], "contaminant_case_ids": []}
        }
        app_ = make_app(fake_db)
        TestClient(app_).delete("/api/v1/ntc/contaminants/329")
        assert ntc_module._contaminant_alert_cache == {}


# ---------------------------------------------------------------------------
# Contaminant alerts endpoint
# ---------------------------------------------------------------------------


class TestContaminantAlerts:
    def setup_method(self):
        invalidate_contaminant_cache()

    async def test_no_contaminants_returns_empty(self, fake_db):
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/contaminant-alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["alerts"] == []
        assert data["contaminant_case_ids"] == []

    async def test_detects_contaminant_above_min_reads(self, fake_db):
        await fake_db["ntc_known_contaminants"].insert_one(
            {
                "taxon_id": 329,
                "taxon_name": "Ralstonia pickettii",
                "superkingdom": "Bacteria",
                "min_reads": 5,
            }
        )
        result = await fake_db["samples"].insert_one(
            make_ntc_doc(
                "NTC-1",
                "case-1",
                "2026-04-01",
                profile=[make_taxon(329, "Ralstonia pickettii", 10)],
            )
        )
        # case_id is now the human-readable string used for icon matching.
        doc = await fake_db["samples"].find_one({"_id": result.inserted_id})
        expected_case_id = doc["case_id"]
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/contaminant-alerts")
        data = resp.json()
        assert len(data["alerts"]) == 1
        assert data["alerts"][0]["taxon_id"] == 329
        assert data["alerts"][0]["case_count"] == 1
        assert expected_case_id in data["contaminant_case_ids"]

    async def test_contaminant_at_or_below_min_reads_not_detected(self, fake_db):
        await fake_db["ntc_known_contaminants"].insert_one(
            {
                "taxon_id": 329,
                "taxon_name": "Ralstonia pickettii",
                "superkingdom": "Bacteria",
                "min_reads": 5,
            }
        )
        # abundance=5, min_reads=5 — must be strictly greater than
        await fake_db["samples"].insert_one(
            make_ntc_doc(
                "NTC-1",
                "case-1",
                "2026-04-01",
                profile=[make_taxon(329, "Ralstonia pickettii", 5)],
            )
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/contaminant-alerts")
        assert resp.json()["alerts"] == []

    async def test_per_contaminant_min_reads_threshold_respected(self, fake_db):
        # Two contaminants with different thresholds
        await fake_db["ntc_known_contaminants"].insert_many(
            [
                {
                    "taxon_id": 329,
                    "taxon_name": "Taxon-A",
                    "superkingdom": "Bacteria",
                    "min_reads": 3,
                },
                {
                    "taxon_id": 1743,
                    "taxon_name": "Taxon-B",
                    "superkingdom": "Bacteria",
                    "min_reads": 20,
                },
            ]
        )
        # Both present, but only Taxon-A is above its threshold
        await fake_db["samples"].insert_one(
            make_ntc_doc(
                "NTC-1",
                "case-1",
                "2026-04-01",
                profile=[
                    make_taxon(329, "Taxon-A", 10),  # > 3 → detected
                    make_taxon(1743, "Taxon-B", 10),  # not > 20 → not detected
                ],
            )
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/contaminant-alerts")
        alert_ids = [a["taxon_id"] for a in resp.json()["alerts"]]
        assert 329 in alert_ids
        assert 1743 not in alert_ids

    async def test_multiple_cases_counted_correctly(self, fake_db):
        await fake_db["ntc_known_contaminants"].insert_one(
            {
                "taxon_id": 329,
                "taxon_name": "Ralstonia pickettii",
                "superkingdom": "Bacteria",
                "min_reads": 3,
            }
        )
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc(
                    "NTC-1",
                    "case-1",
                    "2026-04-01",
                    profile=[make_taxon(329, "Ralstonia pickettii", 10)],
                ),
                make_ntc_doc(
                    "NTC-2",
                    "case-2",
                    "2026-04-02",
                    profile=[make_taxon(329, "Ralstonia pickettii", 8)],
                ),
                make_ntc_doc(
                    "NTC-3",
                    "case-3",
                    "2026-04-03",
                    profile=[make_taxon(329, "Ralstonia pickettii", 2)],
                ),  # below threshold
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/contaminant-alerts")
        alert = resp.json()["alerts"][0]
        assert alert["case_count"] == 2
        assert len(resp.json()["contaminant_case_ids"]) == 2

    async def test_only_kraken2_profiles_checked(self, fake_db):
        await fake_db["ntc_known_contaminants"].insert_one(
            {
                "taxon_id": 329,
                "taxon_name": "Ralstonia pickettii",
                "superkingdom": "Bacteria",
                "min_reads": 3,
            }
        )
        # Contaminant only in centrifuge profile — must not trigger
        doc = {
            "sample_id": "NTC-1",
            "case_id": "case-1",
            "sample_type": "negative_ctrl",
            "material": "DNA",
            "order_date": "2026-04-01",
            "profiles": [
                {
                    "classifier": "centrifuge",
                    "profile": [make_taxon(329, "Ralstonia pickettii", 10)],
                }
            ],
            "taxprofiler": {},
        }
        await fake_db["samples"].insert_one(doc)
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/contaminant-alerts")
        assert resp.json()["alerts"] == []

    async def test_alerts_sorted_by_case_count_descending(self, fake_db):
        await fake_db["ntc_known_contaminants"].insert_many(
            [
                {
                    "taxon_id": 329,
                    "taxon_name": "Taxon-A",
                    "superkingdom": "Bacteria",
                    "min_reads": 3,
                },
                {
                    "taxon_id": 1743,
                    "taxon_name": "Taxon-B",
                    "superkingdom": "Bacteria",
                    "min_reads": 3,
                },
            ]
        )
        # Taxon-B in 3 cases, Taxon-A in 1
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc(
                    "NTC-1",
                    "case-1",
                    "2026-04-01",
                    profile=[
                        make_taxon(329, "Taxon-A", 10),
                        make_taxon(1743, "Taxon-B", 10),
                    ],
                ),
                make_ntc_doc(
                    "NTC-2",
                    "case-2",
                    "2026-04-02",
                    profile=[make_taxon(1743, "Taxon-B", 10)],
                ),
                make_ntc_doc(
                    "NTC-3",
                    "case-3",
                    "2026-04-03",
                    profile=[make_taxon(1743, "Taxon-B", 10)],
                ),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/contaminant-alerts")
        alerts = resp.json()["alerts"]
        assert alerts[0]["taxon_id"] == 1743  # 3 cases
        assert alerts[1]["taxon_id"] == 329  # 1 case

    async def test_result_is_cached(self, fake_db):
        import app.routers.ntc as ntc_module

        app_ = make_app(fake_db)
        client = TestClient(app_)
        client.get("/api/v1/ntc/contaminant-alerts")
        assert ntc_module._contaminant_alert_cache != {}

    async def test_cache_is_returned_on_second_call(self, fake_db):
        import app.routers.ntc as ntc_module

        sentinel = {
            "alerts": [{"taxon_id": 99999}],
            "contaminant_case_ids": ["sentinel"],
        }
        ntc_module._contaminant_alert_cache = {90: sentinel}
        app_ = make_app(fake_db)
        resp = TestClient(app_).get("/api/v1/ntc/contaminant-alerts")
        assert resp.json()["contaminant_case_ids"] == ["sentinel"]


# ---------------------------------------------------------------------------
# Ignorelist exclusion in /ntc/trends
# ---------------------------------------------------------------------------


class TestIgnorelistExclusionInTrends:
    async def test_ignored_taxon_excluded_from_recurring_taxa(self, fake_db):
        await fake_db["ntc_ignorelist"].insert_one(
            {
                "taxon_id": 1743,
                "taxon_name": "Cutibacterium acnes",
            }
        )
        taxon = {
            "taxon_id": 1743,
            "name": "Cutibacterium acnes",
            "abundance": 20,
            "superkingdom": "Bacteria",
            "rank": "species",
        }
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-1", "case-1", "2026-04-01", profile=[taxon]),
                make_ntc_doc("NTC-2", "case-2", "2026-04-02", profile=[taxon]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?material=DNA&min_reads=3&min_case_pct=0.1"
        )
        taxon_ids = [t["taxon_id"] for t in resp.json()["recurring_taxa"]]
        assert 1743 not in taxon_ids

    async def test_ignored_taxon_excluded_from_kingdom_breakdown(self, fake_db):
        await fake_db["ntc_ignorelist"].insert_one(
            {
                "taxon_id": 1743,
                "taxon_name": "Cutibacterium acnes",
            }
        )
        profile = [
            {
                "taxon_id": 1743,
                "name": "Cutibacterium acnes",
                "abundance": 50,
                "superkingdom": "Bacteria",
                "rank": "species",
            },
            {
                "taxon_id": 329,
                "name": "Ralstonia pickettii",
                "abundance": 10,
                "superkingdom": "Bacteria",
                "rank": "species",
            },
        ]
        await fake_db["samples"].insert_one(
            make_ntc_doc("NTC-1", "case-1", "2026-04-01", profile=profile)
        )
        app = make_app(fake_db)
        resp = TestClient(app).get("/api/v1/ntc/trends?material=DNA")
        entry = resp.json()["kingdom_breakdown"][0]
        # Only Ralstonia's 10 reads should count; Cutibacterium's 50 are ignored
        assert entry["Bacteria"] == 10

    async def test_non_ignored_taxon_still_appears(self, fake_db):
        await fake_db["ntc_ignorelist"].insert_one(
            {
                "taxon_id": 1743,
                "taxon_name": "Cutibacterium acnes",
            }
        )
        other = {
            "taxon_id": 329,
            "name": "Ralstonia pickettii",
            "abundance": 20,
            "superkingdom": "Bacteria",
            "rank": "species",
        }
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-1", "case-1", "2026-04-01", profile=[other]),
                make_ntc_doc("NTC-2", "case-2", "2026-04-02", profile=[other]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?material=DNA&min_reads=3&min_case_pct=0.1"
        )
        taxon_ids = [t["taxon_id"] for t in resp.json()["recurring_taxa"]]
        assert 329 in taxon_ids

    async def test_empty_ignorelist_does_not_affect_results(self, fake_db):
        taxon = {
            "taxon_id": 329,
            "name": "Ralstonia pickettii",
            "abundance": 20,
            "superkingdom": "Bacteria",
            "rank": "species",
        }
        await fake_db["samples"].insert_many(
            [
                make_ntc_doc("NTC-1", "case-1", "2026-04-01", profile=[taxon]),
                make_ntc_doc("NTC-2", "case-2", "2026-04-02", profile=[taxon]),
            ]
        )
        app = make_app(fake_db)
        resp = TestClient(app).get(
            "/api/v1/ntc/trends?material=DNA&min_reads=3&min_case_pct=0.1"
        )
        taxon_ids = [t["taxon_id"] for t in resp.json()["recurring_taxa"]]
        assert 329 in taxon_ids
