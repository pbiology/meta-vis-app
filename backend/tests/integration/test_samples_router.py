# tests/integration/test_samples_router.py

import pytest
from bson import ObjectId
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.routers.samples import router
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


async def insert_sample(
    db,
    sample_id="SRR001",
    sample_type="sample",
    material="DNA",
    has_krona=False,
    profiles=None,
):
    case_oid = ObjectId()
    result = await db["samples"].insert_one(
        {
            "case_id": case_oid,
            "case_id_str": "testcase",
            "sample_type": sample_type,
            "material": material,
            "has_krona": has_krona,
            "sample": {"sample_id": sample_id, "sample_source": "blood"},
            "taxprofiler": {"fastp": None, "bowtie2": None, "classifiers": {}},
            "profiles": profiles or [],
            "review": {"reviewed": False},
            "order_date": "2026-01-01",
            "ingested_at": datetime.now(timezone.utc),
        }
    )
    return result.inserted_id, case_oid


# ---------------------------------------------------------------------------
# GET /samples
# ---------------------------------------------------------------------------


class TestListSamples:
    async def test_empty_db_returns_empty(self, client, fake_db):
        resp = client.get("/api/v1/samples")
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0

    async def test_returns_inserted_sample(self, client, fake_db):
        await insert_sample(fake_db, "SRR001")
        resp = client.get("/api/v1/samples")
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["sample"]["sample_id"] == "SRR001"

    async def test_search_filters_by_sample_id(self, client, fake_db):
        await insert_sample(fake_db, "SRR001")
        await insert_sample(fake_db, "SRR002")
        resp = client.get("/api/v1/samples?search=SRR001")
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["sample"]["sample_id"] == "SRR001"

    async def test_filter_sample_type(self, client, fake_db):
        await insert_sample(fake_db, "SRR001", sample_type="sample")
        await insert_sample(fake_db, "CTRL01", sample_type="negative_ctrl")
        resp = client.get("/api/v1/samples?filter=sample")
        assert resp.json()["total"] == 1

    async def test_filter_controls(self, client, fake_db):
        await insert_sample(fake_db, "SRR001", sample_type="sample")
        await insert_sample(fake_db, "CTRL01", sample_type="negative_ctrl")
        resp = client.get("/api/v1/samples?filter=controls")
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["sample"]["sample_id"] == "CTRL01"

    async def test_pagination_fields_present(self, client, fake_db):
        resp = client.get("/api/v1/samples")
        data = resp.json()
        assert "total" in data
        assert "page" in data
        assert "pages" in data


# ---------------------------------------------------------------------------
# GET /samples/{sample_id}
# ---------------------------------------------------------------------------


class TestGetSample:
    async def test_returns_sample(self, client, fake_db):
        oid, _ = await insert_sample(fake_db, "SRR001")
        resp = client.get(f"/api/v1/samples/{oid}")
        assert resp.status_code == 200
        assert resp.json()["sample"]["sample_id"] == "SRR001"

    async def test_unknown_sample_returns_404(self, client, fake_db):
        resp = client.get(f"/api/v1/samples/{ObjectId()}")
        assert resp.status_code == 404

    async def test_invalid_id_returns_422(self, client, fake_db):
        resp = client.get("/api/v1/samples/not-an-objectid")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /samples/{sample_id}/profile
# ---------------------------------------------------------------------------


class TestGetProfile:
    async def test_returns_empty_profiles(self, client, fake_db):
        oid, _ = await insert_sample(fake_db, "SRR001")
        resp = client.get(f"/api/v1/samples/{oid}/profile")
        assert resp.status_code == 200
        assert resp.json()["profiles"] == []

    async def test_returns_profiles(self, client, fake_db):
        profiles = [
            {"classifier": "kraken2", "classifier_db": "k2_pluspf", "profile": []}
        ]
        oid, _ = await insert_sample(fake_db, "SRR001", profiles=profiles)
        resp = client.get(f"/api/v1/samples/{oid}/profile")
        assert len(resp.json()["profiles"]) == 1
        assert resp.json()["profiles"][0]["classifier"] == "kraken2"

    async def test_unknown_sample_returns_404(self, client, fake_db):
        resp = client.get(f"/api/v1/samples/{ObjectId()}/profile")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /samples/{sample_id}/ntc_profiles
# ---------------------------------------------------------------------------


class TestGetNtcProfiles:
    async def test_returns_empty_when_no_ntcs(self, client, fake_db):
        oid, _ = await insert_sample(fake_db, "SRR001", material="DNA")
        resp = client.get(f"/api/v1/samples/{oid}/ntc_profiles")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_ntc_in_same_case(self, client, fake_db):
        # Insert a sample and an NTC in the same case
        case_oid = ObjectId()
        sample_result = await fake_db["samples"].insert_one(
            {
                "case_id": case_oid,
                "case_id_str": "testcase",
                "sample_type": "sample",
                "material": "DNA",
                "has_krona": False,
                "sample": {"sample_id": "SRR001"},
                "profiles": [],
                "review": {"reviewed": False},
                "ingested_at": datetime.now(timezone.utc),
            }
        )
        await fake_db["samples"].insert_one(
            {
                "case_id": case_oid,
                "case_id_str": "testcase",
                "sample_type": "negative_ctrl",
                "material": "DNA",
                "has_krona": False,
                "sample": {"sample_id": "CTRL01"},
                "profiles": [{"classifier": "kraken2", "profile": []}],
                "review": {"reviewed": False},
                "ingested_at": datetime.now(timezone.utc),
            }
        )
        resp = client.get(f"/api/v1/samples/{sample_result.inserted_id}/ntc_profiles")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["sample_id"] == "CTRL01"

    async def test_unknown_sample_returns_404(self, client, fake_db):
        resp = client.get(f"/api/v1/samples/{ObjectId()}/ntc_profiles")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /samples/{sample_id}/krona
# ---------------------------------------------------------------------------


class TestGetKrona:
    async def test_returns_krona_html(self, client, fake_db, fake_blob):
        oid, case_oid = await insert_sample(fake_db, "SRR001", has_krona=True)
        key = f"krona/{case_oid}/kraken2.html"
        await fake_blob.put(key, "<html>krona</html>")
        resp = client.get(f"/api/v1/samples/{oid}/krona?classifier=kraken2")
        assert resp.status_code == 200
        assert "<html>" in resp.text

    async def test_no_krona_returns_404(self, client, fake_db):
        oid, _ = await insert_sample(fake_db, "SRR001", has_krona=False)
        resp = client.get(f"/api/v1/samples/{oid}/krona")
        assert resp.status_code == 404

    async def test_missing_blob_returns_404(self, client, fake_db, fake_blob):
        oid, _ = await insert_sample(fake_db, "SRR001", has_krona=True)
        # Blob not seeded — should 404
        resp = client.get(f"/api/v1/samples/{oid}/krona")
        assert resp.status_code == 404

    async def test_unknown_sample_returns_404(self, client, fake_db):
        resp = client.get(f"/api/v1/samples/{ObjectId()}/krona")
        assert resp.status_code == 404
