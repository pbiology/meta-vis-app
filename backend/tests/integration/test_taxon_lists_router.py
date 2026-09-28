# tests/integration/test_taxon_lists_router.py
#
# The generic taxon-list API, exercised against each system list.

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.utils import get_current_user
from app.database import get_db
from app.routers.taxon_lists import router
from app.taxon_lists.kinds import (
    KNOWN_PATHOGENS,
    NTC_IGNORELIST,
    NTC_KNOWN_CONTAMINANTS,
    OUTBREAK_IGNORELIST,
    SYSTEM_LISTS,
)
from app.taxon_lists.store import seed_system_lists
from tests.helpers import make_user

RALSTONIA = 329
HIV = 11676
MERGED = 999  # merged into RALSTONIA
DELETED = 998


@pytest.fixture
async def db(fake_db):
    await seed_system_lists(fake_db)
    await fake_db["taxa"].insert_many(
        [
            {
                "taxon_id": RALSTONIA,
                "name": "Ralstonia pickettii",
                "superkingdom": "Bacteria",
            },
            {"taxon_id": HIV, "name": "HIV-1", "superkingdom": "Viruses"},
            # A retired ID can linger in `taxa`; taxa_retired must win.
            {"taxon_id": MERGED, "name": "Stale name", "superkingdom": "Bacteria"},
        ]
    )
    await fake_db["taxa_retired"].insert_many(
        [
            {"taxon_id": MERGED, "status": "merged", "merged_into": RALSTONIA},
            {"taxon_id": DELETED, "status": "deleted", "merged_into": None},
        ]
    )
    return fake_db


def client_for(db, role: str = "admin") -> TestClient:
    # Only get_current_user is overridden: require_role runs for real, so the
    # role checks below are the production ones.
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: db
    user = make_user(role)
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def entries_url(list_id: str) -> str:
    return f"/api/v1/taxon-lists/{list_id}/entries"


async def cache_version(db) -> int:
    doc = await db["meta"].find_one({"_id": "cache_version"})
    return doc["version"] if doc else 0


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


class TestLists:
    async def test_system_lists_are_seeded(self, db):
        resp = client_for(db, "reader").get("/api/v1/taxon-lists")
        assert resp.status_code == 200
        assert {row["list_id"] for row in resp.json()} == {
            s.list_id for s in SYSTEM_LISTS
        }
        assert all(row["system"] for row in resp.json())

    async def test_seeding_is_idempotent(self, db):
        before = await db["taxon_lists"].find_one({"list_id": KNOWN_PATHOGENS})
        await seed_system_lists(db)
        after = await db["taxon_lists"].find_one({"list_id": KNOWN_PATHOGENS})
        assert await db["taxon_lists"].count_documents({}) == len(SYSTEM_LISTS)
        assert after["created_at"] == before["created_at"]

    async def test_filter_by_kind(self, db):
        resp = client_for(db).get("/api/v1/taxon-lists", params={"kind": "ntc_ignore"})
        assert [row["list_id"] for row in resp.json()] == [NTC_IGNORELIST]

    async def test_unknown_list_is_404(self, db):
        assert client_for(db).get("/api/v1/taxon-lists/nope").status_code == 404
        assert client_for(db).get(entries_url("nope")).status_code == 404


# ---------------------------------------------------------------------------
# Adding entries
# ---------------------------------------------------------------------------


class TestAddEntry:
    async def test_name_and_superkingdom_come_from_taxa(self, db):
        resp = client_for(db, "writer").post(
            entries_url(KNOWN_PATHOGENS), json={"taxon_id": HIV, "reason": "BSL3"}
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["taxon_name"] == "HIV-1"
        assert body["superkingdom"] == "Viruses"
        assert body["reason"] == "BSL3"
        assert body["added_by"] == "testuser"

    async def test_client_supplied_name_is_rejected(self, db):
        resp = client_for(db).post(
            entries_url(KNOWN_PATHOGENS),
            json={"taxon_id": HIV, "taxon_name": "Something else"},
        )
        assert resp.status_code == 422

    async def test_reader_cannot_add(self, db):
        resp = client_for(db, "reader").post(
            entries_url(KNOWN_PATHOGENS), json={"taxon_id": HIV}
        )
        assert resp.status_code == 403

    async def test_duplicate_on_same_list_is_409(self, db):
        client = client_for(db)
        client.post(entries_url(OUTBREAK_IGNORELIST), json={"taxon_id": HIV})
        resp = client.post(entries_url(OUTBREAK_IGNORELIST), json={"taxon_id": HIV})
        assert resp.status_code == 409

    async def test_same_taxon_on_several_lists(self, db):
        client = client_for(db)
        for list_id in (KNOWN_PATHOGENS, OUTBREAK_IGNORELIST):
            resp = client.post(entries_url(list_id), json={"taxon_id": HIV})
            assert resp.status_code == 201
        assert await db["taxon_list_entries"].count_documents({"taxon_id": HIV}) == 2

    @pytest.mark.parametrize(
        ("first", "second"),
        [
            (NTC_IGNORELIST, NTC_KNOWN_CONTAMINANTS),
            (NTC_KNOWN_CONTAMINANTS, NTC_IGNORELIST),
        ],
    )
    async def test_ntc_ignore_and_contaminants_exclude_each_other(
        self, db, first, second
    ):
        client = client_for(db)
        assert (
            client.post(entries_url(first), json={"taxon_id": RALSTONIA}).status_code
            == 201
        )
        resp = client.post(entries_url(second), json={"taxon_id": RALSTONIA})
        assert resp.status_code == 409

    async def test_contaminant_min_reads_defaults_to_3(self, db):
        resp = client_for(db).post(
            entries_url(NTC_KNOWN_CONTAMINANTS), json={"taxon_id": RALSTONIA}
        )
        assert resp.json()["min_reads"] == 3

    async def test_min_reads_rejected_on_other_kinds(self, db):
        resp = client_for(db).post(
            entries_url(NTC_IGNORELIST), json={"taxon_id": RALSTONIA, "min_reads": 5}
        )
        assert resp.status_code == 422
        assert "min_reads" in resp.json()["detail"]

    async def test_unknown_taxon_is_422(self, db):
        resp = client_for(db).post(
            entries_url(KNOWN_PATHOGENS), json={"taxon_id": 123456}
        )
        assert resp.status_code == 422

    async def test_merged_taxon_points_at_its_replacement(self, db):
        resp = client_for(db).post(
            entries_url(KNOWN_PATHOGENS), json={"taxon_id": MERGED}
        )
        assert resp.status_code == 422
        assert str(RALSTONIA) in resp.json()["detail"]

    async def test_deleted_taxon_is_422(self, db):
        resp = client_for(db).post(
            entries_url(KNOWN_PATHOGENS), json={"taxon_id": DELETED}
        )
        assert resp.status_code == 422

    async def test_add_is_audited(self, db):
        client_for(db).post(entries_url(KNOWN_PATHOGENS), json={"taxon_id": HIV})
        event = await db["audit_log"].find_one({"action": "taxon_list_entry_add"})
        assert event["resource_id"] == f"{KNOWN_PATHOGENS}:{HIV}"
        assert event["detail"]["kind"] == "known_pathogens"

    async def test_analytics_lists_bump_the_cache_version(self, db):
        client_for(db).post(entries_url(OUTBREAK_IGNORELIST), json={"taxon_id": HIV})
        assert await cache_version(db) == 1

    async def test_pathogens_do_not_bump_the_cache_version(self, db):
        client_for(db).post(entries_url(KNOWN_PATHOGENS), json={"taxon_id": HIV})
        assert await cache_version(db) == 0


# ---------------------------------------------------------------------------
# Reading, updating and removing entries
# ---------------------------------------------------------------------------


class TestListEntries:
    async def test_filter_by_superkingdom(self, db):
        client = client_for(db)
        client.post(entries_url(OUTBREAK_IGNORELIST), json={"taxon_id": HIV})
        client.post(entries_url(OUTBREAK_IGNORELIST), json={"taxon_id": RALSTONIA})
        resp = client.get(
            entries_url(OUTBREAK_IGNORELIST), params={"superkingdom": "Viruses"}
        )
        assert [row["taxon_id"] for row in resp.json()] == [HIV]


class TestUpdateEntry:
    async def test_update_min_reads(self, db):
        client = client_for(db, "writer")
        client.post(entries_url(NTC_KNOWN_CONTAMINANTS), json={"taxon_id": RALSTONIA})
        resp = client.patch(
            f"{entries_url(NTC_KNOWN_CONTAMINANTS)}/{RALSTONIA}", json={"min_reads": 10}
        )
        assert resp.status_code == 200
        assert resp.json()["min_reads"] == 10
        assert resp.json()["updated_by"] == "testuser"

    async def test_null_reason_clears_it_and_omitted_fields_are_kept(self, db):
        client = client_for(db)
        client.post(
            entries_url(NTC_KNOWN_CONTAMINANTS),
            json={"taxon_id": RALSTONIA, "reason": "water", "min_reads": 7},
        )
        resp = client.patch(
            f"{entries_url(NTC_KNOWN_CONTAMINANTS)}/{RALSTONIA}", json={"reason": None}
        )
        assert resp.json()["reason"] is None
        assert resp.json()["min_reads"] == 7

    async def test_null_min_reads_is_422(self, db):
        client = client_for(db)
        client.post(entries_url(NTC_KNOWN_CONTAMINANTS), json={"taxon_id": RALSTONIA})
        resp = client.patch(
            f"{entries_url(NTC_KNOWN_CONTAMINANTS)}/{RALSTONIA}",
            json={"min_reads": None},
        )
        assert resp.status_code == 422

    async def test_empty_body_is_422(self, db):
        resp = client_for(db).patch(f"{entries_url(KNOWN_PATHOGENS)}/{HIV}", json={})
        assert resp.status_code == 422

    async def test_missing_entry_is_404(self, db):
        resp = client_for(db).patch(
            f"{entries_url(KNOWN_PATHOGENS)}/{HIV}", json={"reason": "x"}
        )
        assert resp.status_code == 404


class TestRemoveEntry:
    async def test_admin_removes(self, db):
        client = client_for(db)
        client.post(entries_url(KNOWN_PATHOGENS), json={"taxon_id": HIV})
        resp = client.delete(f"{entries_url(KNOWN_PATHOGENS)}/{HIV}")
        assert resp.status_code == 204
        assert await db["taxon_list_entries"].count_documents({}) == 0
        assert await db["audit_log"].find_one({"action": "taxon_list_entry_remove"})

    async def test_writer_cannot_remove(self, db):
        client_for(db).post(entries_url(KNOWN_PATHOGENS), json={"taxon_id": HIV})
        resp = client_for(db, "writer").delete(f"{entries_url(KNOWN_PATHOGENS)}/{HIV}")
        assert resp.status_code == 403
        assert await db["taxon_list_entries"].count_documents({}) == 1

    async def test_removal_only_touches_that_list(self, db):
        client = client_for(db)
        client.post(entries_url(KNOWN_PATHOGENS), json={"taxon_id": HIV})
        client.post(entries_url(OUTBREAK_IGNORELIST), json={"taxon_id": HIV})
        client.delete(f"{entries_url(KNOWN_PATHOGENS)}/{HIV}")
        remaining = await db["taxon_list_entries"].distinct("list_id")
        assert remaining == [OUTBREAK_IGNORELIST]

    async def test_missing_entry_is_404(self, db):
        resp = client_for(db).delete(f"{entries_url(KNOWN_PATHOGENS)}/{HIV}")
        assert resp.status_code == 404
