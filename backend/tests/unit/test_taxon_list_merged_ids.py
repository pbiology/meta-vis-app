# tests/unit/test_taxon_list_merged_ids.py
#
# Lists store current NCBI ids, but a sample classified with an older database
# can report an id NCBI has since merged. Every list consumer must match the
# retired form too.

from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.utils import get_current_user
from app.database import get_db
from app.routers import alerts as alerts_module
from app.routers.cases import router as cases_router
from app.routers.taxon_lists import router as taxon_lists_router
from app.taxon_lists import store
from app.taxon_lists.kinds import KNOWN_PATHOGENS, OUTBREAK_IGNORELIST
from app.taxon_lists.store import seed_system_lists
from tests.helpers import make_user, seed_list_entries

CURRENT = 28116
OLD_A = 1912894
OLD_B = 1912896
RECENT = (date.today() - timedelta(days=2)).isoformat()


@pytest.fixture
async def db(fake_db):
    await fake_db["taxa_retired"].insert_many(
        [
            {"taxon_id": OLD_A, "status": "merged", "merged_into": CURRENT},
            {"taxon_id": OLD_B, "status": "merged", "merged_into": CURRENT},
            {"taxon_id": 5, "status": "deleted", "merged_into": None},
        ]
    )
    return fake_db


def _client(router, db) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: make_user("reader")
    return TestClient(app)


class TestStore:
    async def test_merged_aliases_maps_current_to_old_ids(self, db):
        assert await store.merged_aliases(db, {CURRENT, 999}) == {
            CURRENT: [OLD_A, OLD_B]
        }

    async def test_merged_aliases_of_nothing_is_empty(self, db):
        assert await store.merged_aliases(db, set()) == {}

    async def test_taxon_ids_include_the_retired_ids(self, db):
        await seed_list_entries(
            db, KNOWN_PATHOGENS, {"taxon_id": CURRENT, "taxon_name": "x"}
        )
        assert await store.taxon_ids(db, KNOWN_PATHOGENS) == {CURRENT, OLD_A, OLD_B}


class TestApi:
    async def test_entries_carry_their_merged_ids(self, db):
        await seed_system_lists(db)
        await seed_list_entries(
            db, KNOWN_PATHOGENS, {"taxon_id": CURRENT, "taxon_name": "x"}
        )

        body = (
            _client(taxon_lists_router, db)
            .get(f"/api/v1/taxon-lists/{KNOWN_PATHOGENS}/entries")
            .json()
        )

        assert body["items"][0]["merged_ids"] == [OLD_A, OLD_B]

    async def test_taxon_ids_endpoint_includes_merged_ids(self, db):
        await seed_system_lists(db)
        await seed_list_entries(
            db, KNOWN_PATHOGENS, {"taxon_id": CURRENT, "taxon_name": "x"}
        )

        body = (
            _client(taxon_lists_router, db)
            .get(f"/api/v1/taxon-lists/{KNOWN_PATHOGENS}/taxon-ids")
            .json()
        )

        assert sorted(body["taxon_ids"]) == [CURRENT, OLD_A, OLD_B]


class TestConsumers:
    async def test_pathogen_cases_flags_a_sample_reporting_the_old_id(self, db):
        await seed_list_entries(
            db, KNOWN_PATHOGENS, {"taxon_id": CURRENT, "taxon_name": "x"}
        )
        await db["samples"].insert_one(
            {
                "case_id": "old-db-case",
                "is_latest_analysis": True,
                "all_taxon_ids": [OLD_A],
            }
        )

        resp = _client(cases_router, db).get("/api/v1/cases/pathogen_cases")

        assert resp.json() == {"case_ids": ["old-db-case"]}

    async def test_outbreak_ignorelist_ignores_the_old_id(self, db, monkeypatch):
        alerts_module._cache.clear()
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
        for case_id in ("case-1", "case-2"):
            await db["case_analysis"].insert_one(
                {"case_id": case_id, "is_latest": True, "order_date": RECENT}
            )
            await db["samples"].insert_one(
                {
                    "case_id": case_id,
                    "is_latest_analysis": True,
                    "outbreak_taxa": [
                        {
                            "taxon_id": OLD_A,
                            "name": "Old name",
                            "superkingdom": "Viruses",
                            "rank": "species",
                            "abundance": 50,
                        }
                    ],
                }
            )
        await seed_list_entries(
            db, OUTBREAK_IGNORELIST, {"taxon_id": CURRENT, "taxon_name": "x"}
        )

        resp = _client(alerts_module.router, db).get("/api/v1/alerts/outbreaks")

        outbreaks = [o for r in resp.json()["results"] for o in r["outbreaks"]]
        assert outbreaks == []
        alerts_module._cache.clear()
