# tests/integration/test_cases_router.py

import asyncio
from unittest.mock import patch

import pytest
from bson import ObjectId
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from mongomock.not_implemented import ignore_feature

from app.routers import cases as cases_module
from app.routers.cases import router
from tests.helpers import make_test_app

# Mongomock has no real sessions/transactions; treat them as no-ops so the
# delete handler's `start_session()` / `start_transaction()` calls work.
ignore_feature("session")


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def start_transaction(self):
        return self


class _FakeClient:
    async def start_session(self):
        await asyncio.sleep(0)
        return _FakeSession()


@pytest.fixture(autouse=True)
def _patch_mongo_client():
    with patch.object(cases_module, "get_client", return_value=_FakeClient()):
        yield


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app(fake_db, fake_blob):
    return make_test_app(router, fake_db, fake_blob)


@pytest.fixture
def client(app):
    return TestClient(app)


async def insert_case(
    db,
    case_id="testcase",
    reviewed=False,
    order_date="2026-01-01",
    analysis_type=None,
    subject_id=None,
):
    doc = {
        "case_id": case_id,
        "order_date": order_date,
        "ingested_at": datetime.now(timezone.utc),
        "sample_ids": [],
        "classifiers": [],
        "has_krona": False,
        "pipeline_info": None,
        "sample_count": 0,
        "control_count": 0,
        "sample_names": [],
        "notes": [],
        "review": {
            "reviewed": reviewed,
            "reviewed_by": "alice" if reviewed else None,
            "reviewed_at": None,
            "notes": None,
        },
        "subject_id": subject_id,
    }
    if analysis_type is not None:
        doc["analysis_type"] = analysis_type
    result = await db["cases"].insert_one(doc)
    return result.inserted_id


async def insert_sample(db, case_id, sample_id="SRR001", sample_type="sample"):
    result = await db["samples"].insert_one(
        {
            "case_id": case_id,
            "sample_type": sample_type,
            "material": "DNA",
            "sample": {"sample_id": sample_id, "sample_source": "blood"},
            "taxprofiler": {"fastp": None, "bowtie2": None, "classifiers": {}},
            "profiles": [],
            "has_krona": False,
            "review": {"reviewed": False},
            "ingested_at": datetime.now(timezone.utc),
        }
    )
    return result.inserted_id


# ---------------------------------------------------------------------------
# GET /cases/stats
# ---------------------------------------------------------------------------


class TestCaseStats:
    async def test_empty_db_returns_zeros(self, client, fake_db):
        resp = client.get("/api/v1/cases/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["pending"] == 0
        assert data["reviewed"] == 0
        assert data["pending_shotgun"] == 0
        assert data["pending_amplicon"] == 0

    async def test_counts_correctly(self, client, fake_db):
        await insert_case(fake_db, "case1", reviewed=False)
        await insert_case(fake_db, "case2", reviewed=True)
        resp = client.get("/api/v1/cases/stats")
        data = resp.json()
        assert data["total"] == 2
        assert data["reviewed"] == 1
        assert data["pending"] == 1

    async def test_pending_split_by_analysis_type(self, client, fake_db):
        await insert_case(fake_db, "s1", reviewed=False, analysis_type="shotgun")
        await insert_case(fake_db, "s2", reviewed=False, analysis_type="shotgun")
        await insert_case(fake_db, "a1", reviewed=False, analysis_type="amplicon")
        await insert_case(fake_db, "s3", reviewed=True, analysis_type="shotgun")
        resp = client.get("/api/v1/cases/stats")
        data = resp.json()
        assert data["pending_shotgun"] == 2
        assert data["pending_amplicon"] == 1
        assert data["pending"] == 3
        assert data["reviewed"] == 1


# ---------------------------------------------------------------------------
# GET /cases
# ---------------------------------------------------------------------------


class TestListCases:
    async def test_empty_db_returns_empty_list(self, client, fake_db):
        resp = client.get("/api/v1/cases")
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0

    async def test_returns_ingested_case(self, client, fake_db):
        await insert_case(fake_db, "speedysnake")
        resp = client.get("/api/v1/cases")
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["case_id"] == "speedysnake"

    async def test_search_filters_by_case_id(self, client, fake_db):
        await insert_case(fake_db, "speedy")
        await insert_case(fake_db, "slowtiger")
        resp = client.get("/api/v1/cases?search=speedy")
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["case_id"] == "speedy"

    async def test_pagination_total_correct(self, client, fake_db):
        for i in range(3):
            await insert_case(fake_db, f"case{i}")
        resp = client.get("/api/v1/cases")
        assert resp.json()["total"] == 3


# ---------------------------------------------------------------------------
# GET /cases/{case_id}
# ---------------------------------------------------------------------------


class TestGetCase:
    async def test_returns_case(self, client, fake_db):
        await insert_case(fake_db, "mycase")
        resp = client.get("/api/v1/cases/mycase")
        assert resp.status_code == 200
        assert resp.json()["case_id"] == "mycase"

    async def test_unknown_case_returns_404(self, client, fake_db):
        resp = client.get("/api/v1/cases/nonexistent")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/samples
# ---------------------------------------------------------------------------


class TestListSamplesForCase:
    async def test_returns_samples(self, client, fake_db):
        await insert_case(fake_db, "testcase")
        await insert_sample(fake_db, "testcase", "SRR001")
        resp = client.get("/api/v1/cases/testcase/samples")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["sample"]["sample_id"] == "SRR001"

    async def test_unknown_case_returns_404(self, client, fake_db):
        resp = client.get("/api/v1/cases/nonexistent/samples")
        assert resp.status_code == 404

    async def test_type_filter_controls(self, client, fake_db):
        await insert_case(fake_db, "testcase")
        await insert_sample(fake_db, "testcase", "SRR001", sample_type="sample")
        await insert_sample(fake_db, "testcase", "CTRL01", sample_type="negative_ctrl")
        resp = client.get("/api/v1/cases/testcase/samples?type=controls")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["sample"]["sample_id"] == "CTRL01"


# ---------------------------------------------------------------------------
# PATCH /cases/{case_id}/review
# ---------------------------------------------------------------------------


class TestReviewCase:
    async def test_marks_case_as_reviewed(self, client, fake_db):
        await insert_case(fake_db, "testcase", reviewed=False)
        resp = client.patch("/api/v1/cases/testcase/review", json={})
        assert resp.status_code == 200
        assert resp.json()["reviewed"] is True
        assert resp.json()["reviewed_by"] == "testuser"

    async def test_unknown_case_returns_404(self, client, fake_db):
        resp = client.patch("/api/v1/cases/nonexistent/review", json={})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /cases/{case_id}/review
# ---------------------------------------------------------------------------


class TestUnreviewCase:
    async def test_removes_review(self, client, fake_db):
        await insert_case(fake_db, "testcase", reviewed=True)
        resp = client.delete("/api/v1/cases/testcase/review")
        assert resp.status_code == 200
        assert resp.json()["reviewed"] is False

    async def test_unknown_case_returns_404(self, client, fake_db):
        resp = client.delete("/api/v1/cases/nonexistent/review")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /cases/{case_id}/notes
# ---------------------------------------------------------------------------


class TestAddNote:
    async def test_adds_note(self, client, fake_db):
        await insert_case(fake_db, "testcase")
        resp = client.post("/api/v1/cases/testcase/notes", json={"text": "Looks clean"})
        assert resp.status_code == 200
        assert resp.json()["text"] == "Looks clean"
        assert resp.json()["author"] == "testuser"
        assert resp.json()["id"] is not None

    async def test_empty_note_returns_422(self, client, fake_db):
        await insert_case(fake_db, "testcase")
        resp = client.post("/api/v1/cases/testcase/notes", json={"text": "  "})
        assert resp.status_code == 422

    async def test_unknown_case_returns_404(self, client, fake_db):
        resp = client.post("/api/v1/cases/nonexistent/notes", json={"text": "hi"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /cases/{case_id}/notes/{note_id}
# ---------------------------------------------------------------------------


class TestDeleteNote:
    async def test_deletes_note(self, client, fake_db):
        await insert_case(fake_db, "testcase")
        add_resp = client.post(
            "/api/v1/cases/testcase/notes", json={"text": "First note"}
        )
        note_id = add_resp.json()["id"]
        resp = client.delete(f"/api/v1/cases/testcase/notes/{note_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True

    async def test_unknown_note_id_returns_404(self, client, fake_db):
        await insert_case(fake_db, "testcase")
        resp = client.delete(
            "/api/v1/cases/testcase/notes/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /cases/{case_id}
# ---------------------------------------------------------------------------


class TestDeleteCase:
    async def test_deletes_case(self, client, fake_db):
        await insert_case(fake_db, "testcase")
        resp = client.delete("/api/v1/cases/testcase")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        # Confirm it's gone
        assert client.get("/api/v1/cases/testcase").status_code == 404

    async def test_unknown_case_returns_404(self, client, fake_db):
        resp = client.delete("/api/v1/cases/nonexistent")
        assert resp.status_code == 404

    async def test_orphan_subject_is_pruned(self, client, fake_db):
        # Subject is referenced only by this case → should be deleted with it.
        subj_oid = ObjectId()
        await fake_db["subjects"].insert_one(
            {"_id": subj_oid, "subject_id": "SUBJ-orphan", "sex": "F"}
        )
        await insert_case(fake_db, "soleowner", subject_id=subj_oid)

        resp = client.delete("/api/v1/cases/soleowner")
        assert resp.status_code == 200
        assert await fake_db["subjects"].find_one({"_id": subj_oid}) is None

    async def test_shared_subject_is_kept(self, client, fake_db):
        # Subject is referenced by another case → must survive.
        subj_oid = ObjectId()
        await fake_db["subjects"].insert_one(
            {"_id": subj_oid, "subject_id": "SUBJ-shared", "sex": "M"}
        )
        await insert_case(fake_db, "casea", subject_id=subj_oid)
        await insert_case(fake_db, "caseb", subject_id=subj_oid)

        resp = client.delete("/api/v1/cases/casea")
        assert resp.status_code == 200
        assert await fake_db["subjects"].find_one({"_id": subj_oid}) is not None

    async def test_cascades_to_samples_and_metaval(self, client, fake_db):
        await insert_case(fake_db, "cascadecase")
        await fake_db["samples"].insert_many(
            [
                {"case_id": "cascadecase", "sample_id": "s1"},
                {"case_id": "cascadecase", "sample_id": "s2"},
            ]
        )
        await fake_db["metaval_results"].insert_one(
            {"case_id": "cascadecase", "taxid": 9606}
        )

        resp = client.delete("/api/v1/cases/cascadecase")
        assert resp.status_code == 200
        assert await fake_db["samples"].count_documents({"case_id": "cascadecase"}) == 0
        assert (
            await fake_db["metaval_results"].count_documents({"case_id": "cascadecase"})
            == 0
        )

    async def test_control_only_case_skips_subject_cleanup(self, client, fake_db):
        # Case with subject_id=None (control-only) deletes cleanly.
        await insert_case(fake_db, "controlonly", subject_id=None)
        resp = client.delete("/api/v1/cases/controlonly")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/krona
# ---------------------------------------------------------------------------


class TestGetCaseKrona:
    async def test_serves_krona_html(self, client, fake_db, fake_blob):
        await insert_case(fake_db, "testcase")
        await fake_blob.put("krona/testcase/kraken2.html", "<html>krona</html>")
        resp = client.get("/api/v1/cases/testcase/krona?classifier=kraken2")
        assert resp.status_code == 200
        assert "<html>" in resp.text

    async def test_unknown_case_returns_404(self, client, fake_db):
        resp = client.get("/api/v1/cases/nonexistent/krona")
        assert resp.status_code == 404

    async def test_missing_blob_returns_404(self, client, fake_db):
        await insert_case(fake_db, "testcase")
        resp = client.get("/api/v1/cases/testcase/krona?classifier=kraken2")
        assert resp.status_code == 404

    async def test_default_classifier_is_kraken2(self, client, fake_db, fake_blob):
        await insert_case(fake_db, "testcase")
        await fake_blob.put("krona/testcase/kraken2.html", "<html>krona</html>")
        resp = client.get("/api/v1/cases/testcase/krona")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/samples — extended coverage
# ---------------------------------------------------------------------------


class TestListSamplesExtended:
    async def test_type_filter_sample(self, client, fake_db):
        await insert_case(fake_db, "testcase")
        await insert_sample(fake_db, "testcase", "SRR001", sample_type="sample")
        await insert_sample(fake_db, "testcase", "CTRL01", sample_type="negative_ctrl")
        resp = client.get("/api/v1/cases/testcase/samples?type=sample")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["sample"]["sample_id"] == "SRR001"

    async def test_profiles_produce_top_taxa(self, client, fake_db):
        await insert_case(fake_db, "testcase")
        await fake_db["samples"].insert_one(
            {
                "case_id": "testcase",
                "sample_type": "sample",
                "material": "DNA",
                "sample": {"sample_id": "SRR001"},
                "taxprofiler": {"classifiers": {}},
                "profiles": [
                    {
                        "classifier": "kraken2",
                        "classifier_db": "k2_pluspf",
                        "profile": [
                            {
                                "taxon_id": 9606,
                                "name": "Homo sapiens",
                                "abundance": 300.0,
                                "superkingdom": "Eukaryota",
                            },
                            {
                                "taxon_id": 1279,
                                "name": "Staphylococcus",
                                "abundance": 400.0,
                                "superkingdom": "Bacteria",
                            },
                        ],
                    }
                ],
                "has_krona": False,
                "review": {"reviewed": False},
                "ingested_at": datetime.now(timezone.utc),
            }
        )
        resp = client.get("/api/v1/cases/testcase/samples")
        assert resp.status_code == 200
        top = resp.json()[0]["top_taxa"]["kraken2"]
        assert top[0]["name"] == "Staphylococcus"

    async def test_subject_id_serialised(self, client, fake_db):
        await insert_case(fake_db, "testcase")
        subject_oid = ObjectId()
        await fake_db["samples"].insert_one(
            {
                "case_id": "testcase",
                "subject_id": subject_oid,
                "sample_type": "sample",
                "material": "DNA",
                "sample": {"sample_id": "SRR001"},
                "taxprofiler": {"classifiers": {}},
                "profiles": [],
                "has_krona": False,
                "review": {"reviewed": False},
                "ingested_at": datetime.now(timezone.utc),
            }
        )
        resp = client.get("/api/v1/cases/testcase/samples")
        assert resp.json()[0]["subject_id"] == str(subject_oid)


# ---------------------------------------------------------------------------
# DELETE /cases/{case_id}/notes — permission checks
# ---------------------------------------------------------------------------


class TestDeleteNotePermissions:
    async def test_non_admin_cannot_delete_other_users_note(self, fake_db, fake_blob):
        app = make_test_app(router, fake_db, fake_blob, role="writer")
        client = TestClient(app)
        await insert_case(fake_db, "testcase")
        note_id = "aaaaaaaa-0000-0000-0000-000000000001"
        await fake_db["cases"].update_one(
            {"case_id": "testcase"},
            {
                "$push": {
                    "notes": {
                        "id": note_id,
                        "text": "Other user's note",
                        "author": "otheruser",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                }
            },
        )
        resp = client.delete(f"/api/v1/cases/testcase/notes/{note_id}")
        assert resp.status_code == 403

    async def test_owner_can_delete_own_note(self, client, fake_db):
        await insert_case(fake_db, "testcase")
        note_id = "aaaaaaaa-0000-0000-0000-000000000002"
        await fake_db["cases"].update_one(
            {"case_id": "testcase"},
            {
                "$push": {
                    "notes": {
                        "id": note_id,
                        "text": "My note",
                        "author": "testuser",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                }
            },
        )
        resp = client.delete(f"/api/v1/cases/testcase/notes/{note_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


# ---------------------------------------------------------------------------
# PATCH /cases/{case_id}/report
# ---------------------------------------------------------------------------


async def _insert_case_with_samples(db, case_id="testcase", sample_ids=("S1", "S2")):
    await insert_case(db, case_id)
    for sid in sample_ids:
        await db["samples"].insert_one(
            {
                "case_id": case_id,
                "sample_id": sid,
                "sample_type": "sample",
                "ingested_at": datetime.now(timezone.utc),
            }
        )


class TestUpdateReport:
    async def test_persists_selections(self, client, fake_db):
        await _insert_case_with_samples(fake_db, "testcase", ("S1", "S2"))
        resp = client.patch(
            "/api/v1/cases/testcase/report",
            json={"selections": {"S1": [11676, 562], "S2": [9606]}},
        )
        assert resp.status_code == 200
        assert resp.json()["selections"] == {"S1": [11676, 562], "S2": [9606]}
        doc = await fake_db["cases"].find_one({"case_id": "testcase"})
        assert doc["report_selections"] == {"S1": [11676, 562], "S2": [9606]}

    async def test_replaces_existing_selections(self, client, fake_db):
        await _insert_case_with_samples(fake_db, "testcase", ("S1", "S2"))
        client.patch(
            "/api/v1/cases/testcase/report",
            json={"selections": {"S1": [1, 2, 3]}},
        )
        resp = client.patch(
            "/api/v1/cases/testcase/report",
            json={"selections": {"S2": [42]}},
        )
        assert resp.status_code == 200
        doc = await fake_db["cases"].find_one({"case_id": "testcase"})
        assert doc["report_selections"] == {"S2": [42]}

    async def test_rejects_unknown_sample_id(self, client, fake_db):
        await _insert_case_with_samples(fake_db, "testcase", ("S1",))
        resp = client.patch(
            "/api/v1/cases/testcase/report",
            json={"selections": {"S1": [1], "S99": [2]}},
        )
        assert resp.status_code == 422
        assert "S99" in resp.json()["detail"]

    def test_rejects_missing_case(self, client):
        resp = client.patch(
            "/api/v1/cases/nonexistent/report",
            json={"selections": {}},
        )
        assert resp.status_code == 404

    async def test_reader_forbidden(self, fake_db, fake_blob):
        app = make_test_app(router, fake_db, fake_blob, role="reader")
        reader_client = TestClient(app)
        await _insert_case_with_samples(fake_db, "testcase", ("S1",))
        resp = reader_client.patch(
            "/api/v1/cases/testcase/report",
            json={"selections": {"S1": [1]}},
        )
        assert resp.status_code == 403
