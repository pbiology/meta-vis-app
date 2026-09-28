# tests/unit/test_taxon_list_consumers.py
#
# The outbreak ignorelist and known-pathogens lists reach the analytics that
# read them. (The NTC lists are covered in test_ntc_list_consumers.py.)

from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.utils import get_current_user
from app.database import get_db
from app.routers import alerts as alerts_module
from app.routers.cases import router as cases_router
from app.taxon_lists.kinds import KNOWN_PATHOGENS, OUTBREAK_IGNORELIST
from tests.helpers import make_user, seed_list_entries

HIV = 11676
RECENT = (date.today() - timedelta(days=2)).isoformat()


def _client(router, db) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: make_user("reader")
    return TestClient(app)


class TestOutbreakIgnorelist:
    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
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
        yield
        alerts_module._cache.clear()

    async def _two_cases_with_hiv(self, db):
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
                            "taxon_id": HIV,
                            "name": "HIV-1",
                            "superkingdom": "Viruses",
                            "rank": "species",
                            "abundance": 50,
                        }
                    ],
                }
            )

    def _outbreak_taxa(self, db) -> list[int]:
        resp = _client(alerts_module.router, db).get("/api/v1/alerts/outbreaks")
        assert resp.status_code == 200
        return [o["taxon_id"] for r in resp.json()["results"] for o in r["outbreaks"]]

    async def test_taxon_flagged_when_not_ignored(self, fake_db):
        await self._two_cases_with_hiv(fake_db)
        assert self._outbreak_taxa(fake_db) == [HIV]

    async def test_ignored_taxon_is_not_flagged(self, fake_db):
        await self._two_cases_with_hiv(fake_db)
        await seed_list_entries(
            fake_db, OUTBREAK_IGNORELIST, {"taxon_id": HIV, "taxon_name": "HIV-1"}
        )
        assert self._outbreak_taxa(fake_db) == []


class TestPathogenCases:
    async def _sample(self, db, case_id: str, latest: bool = True):
        await db["samples"].insert_one(
            {"case_id": case_id, "is_latest_analysis": latest, "all_taxon_ids": [HIV]}
        )

    async def test_no_pathogens_listed_returns_empty(self, fake_db):
        await self._sample(fake_db, "case-1")
        resp = _client(cases_router, fake_db).get("/api/v1/cases/pathogen_cases")
        assert resp.json() == {"case_ids": []}

    async def test_cases_carrying_a_listed_pathogen(self, fake_db):
        await seed_list_entries(
            fake_db, KNOWN_PATHOGENS, {"taxon_id": HIV, "taxon_name": "HIV-1"}
        )
        await self._sample(fake_db, "case-1")
        await self._sample(fake_db, "case-old", latest=False)
        resp = _client(cases_router, fake_db).get("/api/v1/cases/pathogen_cases")
        assert resp.json() == {"case_ids": ["case-1"]}
