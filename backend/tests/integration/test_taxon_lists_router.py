# tests/integration/test_taxon_lists_router.py
#
# The generic taxon-list API, exercised against each system list.

from contextlib import asynccontextmanager
from datetime import datetime, timezone

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

    async def test_merged_taxon_is_added_as_its_current_id(self, db):
        resp = client_for(db).post(
            entries_url(KNOWN_PATHOGENS), json={"taxon_id": MERGED}
        )
        assert resp.status_code == 201
        assert resp.json()["taxon_id"] == RALSTONIA
        assert resp.json()["taxon_name"] == "Ralstonia pickettii"
        event = await db["audit_log"].find_one({"action": "taxon_list_entry_add"})
        assert event["detail"]["replaced_merged_id"] == MERGED

    async def test_merged_taxon_whose_current_id_is_on_the_list_is_409(self, db):
        client = client_for(db)
        client.post(entries_url(KNOWN_PATHOGENS), json={"taxon_id": RALSTONIA})
        resp = client.post(entries_url(KNOWN_PATHOGENS), json={"taxon_id": MERGED})
        assert resp.status_code == 409
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
        assert [row["taxon_id"] for row in resp.json()["items"]] == [HIV]


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


# ---------------------------------------------------------------------------
# User-created lists (display filters)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_transactions(monkeypatch):
    # mongomock has no sessions: run list deletes without a transaction, the
    # same path a standalone mongod takes.
    import app.taxon_lists.service as service_module

    monkeypatch.setattr(
        service_module, "maybe_transaction", _no_transaction, raising=True
    )
    monkeypatch.setattr(service_module, "get_client", lambda: None)


@asynccontextmanager
async def _no_transaction(_client):
    yield None


def create_filter(db, name: str = "Skin flora", role: str = "writer") -> dict:
    resp = client_for(db, role).post(
        "/api/v1/taxon-lists", json={"kind": "display_filter", "name": name}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestCreateList:
    async def test_writer_creates_a_display_filter(self, db):
        created = create_filter(db)
        assert created["list_id"].startswith("df-")
        assert created["system"] is False
        assert created["created_by"] == "testuser"
        assert await db["audit_log"].find_one({"action": "taxon_list_create"})

    async def test_reader_cannot_create(self, db):
        resp = client_for(db, "reader").post(
            "/api/v1/taxon-lists", json={"kind": "display_filter", "name": "x"}
        )
        assert resp.status_code == 403

    async def test_system_kinds_cannot_be_created(self, db):
        resp = client_for(db).post(
            "/api/v1/taxon-lists", json={"kind": "known_pathogens", "name": "Mine"}
        )
        assert resp.status_code == 422

    async def test_blank_name_is_rejected(self, db):
        resp = client_for(db).post(
            "/api/v1/taxon-lists", json={"kind": "display_filter", "name": ""}
        )
        assert resp.status_code == 422

    async def test_overview_includes_entry_counts(self, db):
        list_id = create_filter(db)["list_id"]
        client_for(db).post(entries_url(list_id), json={"taxon_id": HIV})

        resp = client_for(db, "reader").get(
            "/api/v1/taxon-lists", params={"kind": "display_filter"}
        )

        assert [(r["list_id"], r["entry_count"]) for r in resp.json()] == [(list_id, 1)]


class TestUpdateList:
    async def test_writer_renames(self, db):
        list_id = create_filter(db)["list_id"]
        resp = client_for(db, "writer").patch(
            f"/api/v1/taxon-lists/{list_id}", json={"name": "Skin commensals"}
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Skin commensals"
        assert resp.json()["list_id"] == list_id

    async def test_system_list_cannot_be_renamed(self, db):
        resp = client_for(db).patch(
            f"/api/v1/taxon-lists/{KNOWN_PATHOGENS}", json={"name": "x"}
        )
        assert resp.status_code == 403

    async def test_null_name_is_rejected(self, db):
        list_id = create_filter(db)["list_id"]
        resp = client_for(db).patch(
            f"/api/v1/taxon-lists/{list_id}", json={"name": None}
        )
        assert resp.status_code == 422


class TestDeleteList:
    async def test_admin_deletes_list_entries_and_active_preferences(self, db):
        list_id = create_filter(db)["list_id"]
        client_for(db).post(entries_url(list_id), json={"taxon_id": HIV})
        await db["users"].insert_one(
            {
                "sub": "sub-bob",
                "preferences": {"active_display_filters": [list_id, "df-other"]},
            }
        )

        resp = client_for(db, "admin").delete(f"/api/v1/taxon-lists/{list_id}")

        assert resp.status_code == 204
        assert await db["taxon_lists"].find_one({"list_id": list_id}) is None
        assert await db["taxon_list_entries"].count_documents({"list_id": list_id}) == 0
        bob = await db["users"].find_one({"sub": "sub-bob"})
        assert bob["preferences"]["active_display_filters"] == ["df-other"]
        event = await db["audit_log"].find_one({"action": "taxon_list_delete"})
        assert event["detail"]["removed_entries"] == 1

    async def test_writer_cannot_delete(self, db):
        list_id = create_filter(db)["list_id"]
        resp = client_for(db, "writer").delete(f"/api/v1/taxon-lists/{list_id}")
        assert resp.status_code == 403

    async def test_system_list_cannot_be_deleted(self, db):
        resp = client_for(db).delete(f"/api/v1/taxon-lists/{KNOWN_PATHOGENS}")
        assert resp.status_code == 403
        assert await db["taxon_lists"].find_one({"list_id": KNOWN_PATHOGENS})


class TestDisplayFilterEntries:
    async def test_entries_do_not_bump_the_analytics_cache(self, db):
        list_id = create_filter(db)["list_id"]
        client_for(db).post(entries_url(list_id), json={"taxon_id": HIV})
        assert await cache_version(db) == 0

    async def test_display_filter_and_ntc_ignore_do_not_conflict(self, db):
        list_id = create_filter(db)["list_id"]
        client = client_for(db)
        client.post(entries_url(NTC_IGNORELIST), json={"taxon_id": RALSTONIA})
        resp = client.post(entries_url(list_id), json={"taxon_id": RALSTONIA})
        assert resp.status_code == 201


class TestBulkAdd:
    def _bulk(self, db, list_id, role="writer", **body):
        return client_for(db, role).post(f"{entries_url(list_id)}/bulk", json=body)

    async def test_dry_run_reports_every_id_and_writes_nothing(self, db):
        list_id = create_filter(db)["list_id"]
        client_for(db).post(entries_url(list_id), json={"taxon_id": HIV})

        resp = self._bulk(
            db,
            list_id,
            taxon_ids=[RALSTONIA, HIV, MERGED, DELETED, 123456],
            dry_run=True,
        )

        assert resp.status_code == 200
        report = resp.json()
        # MERGED was merged into RALSTONIA, also in the paste: one entry.
        assert report["to_add_count"] == 1
        assert report["to_add_sample"][0]["taxon_name"] == "Ralstonia pickettii"
        assert report["already_on_list"] == [HIV]
        assert report["replaced"] == [{"taxon_id": MERGED, "merged_into": RALSTONIA}]
        assert {r["taxon_id"]: r["reason"] for r in report["rejected"]} == {
            DELETED: "deleted",
            123456: "not_in_taxonomy",
        }
        assert report["added"] == 0
        assert await db["taxon_list_entries"].count_documents({"list_id": list_id}) == 1

    async def test_real_run_adds_all_valid_taxa_with_the_reason(self, db):
        list_id = create_filter(db)["list_id"]

        resp = self._bulk(db, list_id, taxon_ids=[RALSTONIA, HIV], reason="Skin")

        assert resp.status_code == 200
        assert resp.json()["added"] == 2
        entries = (
            await db["taxon_list_entries"].find({"list_id": list_id}).to_list(None)
        )
        assert sorted(e["taxon_id"] for e in entries) == [RALSTONIA, HIV]
        assert {e["reason"] for e in entries} == {"Skin"}

    async def test_already_on_list_is_skipped_not_an_error(self, db):
        list_id = create_filter(db)["list_id"]
        client_for(db).post(entries_url(list_id), json={"taxon_id": HIV})

        resp = self._bulk(db, list_id, taxon_ids=[HIV, RALSTONIA])

        assert resp.status_code == 200
        assert resp.json()["added"] == 1

    async def test_any_rejection_on_a_real_run_adds_nothing(self, db):
        list_id = create_filter(db)["list_id"]

        resp = self._bulk(db, list_id, taxon_ids=[RALSTONIA, 123456])

        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert [r["taxon_id"] for r in detail["report"]["rejected"]] == [123456]
        assert await db["taxon_list_entries"].count_documents({"list_id": list_id}) == 0

    async def test_one_audit_event_and_one_cache_bump_per_batch(self, db):
        self._bulk(db, OUTBREAK_IGNORELIST, taxon_ids=[RALSTONIA, HIV])

        events = (
            await db["audit_log"]
            .find({"action": {"$regex": "^taxon_list_entry"}})
            .to_list(None)
        )
        assert [e["action"] for e in events] == ["taxon_list_entry_bulk_add"]
        assert events[0]["detail"]["taxon_ids"] == [RALSTONIA, HIV]
        assert await cache_version(db) == 1

    async def test_contaminant_defaults_apply_to_every_entry(self, db):
        self._bulk(db, NTC_KNOWN_CONTAMINANTS, taxon_ids=[RALSTONIA, HIV], min_reads=7)
        entries = (
            await db["taxon_list_entries"]
            .find({"list_id": NTC_KNOWN_CONTAMINANTS})
            .to_list(None)
        )
        assert {e["min_reads"] for e in entries} == {7}

    async def test_reader_cannot_bulk_add(self, db):
        list_id = create_filter(db)["list_id"]
        resp = self._bulk(db, list_id, role="reader", taxon_ids=[HIV])
        assert resp.status_code == 403

    async def test_batch_size_is_capped(self, db):
        list_id = create_filter(db)["list_id"]
        resp = self._bulk(db, list_id, taxon_ids=list(range(1, 75_002)))
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Large lists — nothing is silently capped
# ---------------------------------------------------------------------------


async def _seed_large_list(db, list_id: str, n: int) -> None:
    await db["taxon_list_entries"].insert_many(
        [
            {
                "list_id": list_id,
                "taxon_id": i,
                "taxon_name": f"Taxon {i}",
                "added_by": "test",
                "added_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            }
            for i in range(1, n + 1)
        ]
    )


class TestBulkReplacement:
    async def test_merged_ids_are_added_as_current_and_audited(self, db):
        list_id = create_filter(db)["list_id"]

        resp = TestBulkAdd()._bulk(db, list_id, taxon_ids=[MERGED, HIV])

        assert resp.status_code == 200
        entries = await db["taxon_list_entries"].distinct(
            "taxon_id", {"list_id": list_id}
        )
        assert sorted(entries) == [RALSTONIA, HIV]
        event = await db["audit_log"].find_one({"action": "taxon_list_entry_bulk_add"})
        assert event["detail"]["replaced"] == [[MERGED, RALSTONIA]]


class TestLargeLists:
    async def test_taxon_ids_endpoint_returns_every_id_past_the_old_cap(self, db):
        await _seed_large_list(db, KNOWN_PATHOGENS, 12_000)
        resp = client_for(db, "reader").get(
            f"/api/v1/taxon-lists/{KNOWN_PATHOGENS}/taxon-ids"
        )
        body = resp.json()
        assert body["count"] == 12_000
        assert len(body["taxon_ids"]) == 12_000

    async def test_store_reads_are_uncapped(self, db):
        from app.models.taxon_list import TaxonListEntry
        from app.taxon_lists import store

        await _seed_large_list(db, NTC_IGNORELIST, 12_000)
        assert len(await store.taxon_ids(db, NTC_IGNORELIST)) == 12_000
        entries = await store.list_entries(db, NTC_IGNORELIST, model=TaxonListEntry)
        assert len(entries) == 12_000

    async def test_entries_are_paged_with_a_total(self, db):
        await _seed_large_list(db, KNOWN_PATHOGENS, 250)
        resp = client_for(db).get(
            entries_url(KNOWN_PATHOGENS), params={"offset": 200, "limit": 100}
        )
        body = resp.json()
        assert body["total"] == 250
        assert len(body["items"]) == 50
        # Same added_at throughout: taxon_id breaks the tie deterministically.
        assert body["items"][0]["taxon_id"] == 201

    async def test_search_matches_name_or_exact_id(self, db):
        await _seed_large_list(db, KNOWN_PATHOGENS, 30)
        client = client_for(db)

        by_name = client.get(entries_url(KNOWN_PATHOGENS), params={"q": "taxon 2"})
        by_id = client.get(entries_url(KNOWN_PATHOGENS), params={"q": "7"})

        assert by_name.json()["total"] == 11  # 2, 20–29
        # A number matches the exact id and any name containing it.
        assert [e["taxon_id"] for e in by_id.json()["items"]] == [7, 17, 27]

    async def test_page_size_is_bounded(self, db):
        resp = client_for(db).get(
            entries_url(KNOWN_PATHOGENS), params={"limit": 10_001}
        )
        assert resp.status_code == 422

    async def test_bulk_preview_names_a_sample_but_counts_everything(self, db):
        list_id = create_filter(db)["list_id"]
        await db["taxa"].insert_many(
            [
                {"taxon_id": 100_000 + i, "name": f"T{i}", "superkingdom": "Bacteria"}
                for i in range(150)
            ]
        )
        ids = [100_000 + i for i in range(150)]

        report = TestBulkAdd()._bulk(db, list_id, taxon_ids=ids, dry_run=True).json()

        assert report["to_add_count"] == 150
        assert len(report["to_add_sample"]) == 100
