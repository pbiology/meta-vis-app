# tests/integration/test_metaval_router.py

import pytest
from bson import ObjectId
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.routers.metaval import router
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


async def insert_metaval(
    db,
    blob_store,
    sample_id=None,
    taxon_name="Shigella-virus-Moo19",
    classifier="kraken2",
    with_reads=True,
    with_igv=True,
):
    case_id = "testcase"
    sample_oid = ObjectId(sample_id) if sample_id else ObjectId()

    reads_keys = {}
    if with_reads:
        read_key = (
            f"verification_data/{case_id}/SRR001/{classifier}/{taxon_name}_read_1.fa"
        )
        await blob_store.put(read_key, ">READ_1\nATCGATCG\n")
        reads_keys["read_1_key"] = read_key

    organisms = []
    if with_igv:
        igv_key = f"igv/{case_id}/SRR001/{classifier}/Shigella-virus-Moo19.html"
        await blob_store.put(igv_key, "<html>igv</html>")
        organisms.append(
            {
                "organism_name": "Shigella-virus-Moo19",
                "igv_key": igv_key,
                "igv_file_size_bytes": 100,
                "igv_too_large": False,
            }
        )

    result = await db["metaval_results"].insert_one(
        {
            # Ingest stamps the producing analysis on every metaval document.
            # Keeping it here means the serialiser is exercised against the
            # real shape — a raw ObjectId left in the response fails JSON
            # encoding for the whole endpoint.
            "analysis_id": ObjectId(),
            "case_id": case_id,
            "sample_id": sample_oid,
            "sample_name": "SRR001",
            "classifier": classifier,
            "taxon_id": 2886042,
            "taxon_name": taxon_name,
            "organisms": organisms,
            "blast": {"blastn": [], "blastx": []},
            "verification_data": {
                "type": "raw_reads",
                "count": 20,
                "avg_length": 150.0,
                "file_count": 2,
                **reads_keys,
            },
            "ingested_at": datetime.now(timezone.utc),
        }
    )
    return result.inserted_id, sample_oid


# ---------------------------------------------------------------------------
# GET /metaval/sample/{sample_id}
# ---------------------------------------------------------------------------


class TestListMetavalForSample:
    async def test_returns_results_for_sample(self, client, fake_db, fake_blob):
        oid, sample_oid = await insert_metaval(fake_db, fake_blob)
        resp = client.get(f"/api/v1/metaval/sample/{sample_oid}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["taxon_name"] == "Shigella-virus-Moo19"

    async def test_invalid_id_returns_422(self, client, fake_db):
        resp = client.get("/api/v1/metaval/sample/not-an-objectid")
        assert resp.status_code == 422

    async def test_unknown_sample_returns_empty_list(self, client, fake_db):
        resp = client.get(f"/api/v1/metaval/sample/{ObjectId()}")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /metaval/{metaval_id}
# ---------------------------------------------------------------------------


class TestGetMetaval:
    async def test_returns_result(self, client, fake_db, fake_blob):
        oid, _ = await insert_metaval(fake_db, fake_blob)
        resp = client.get(f"/api/v1/metaval/{oid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["taxon_name"] == "Shigella-virus-Moo19"
        assert data["classifier"] == "kraken2"

    async def test_serialise_strips_igv_key(self, client, fake_db, fake_blob):
        oid, _ = await insert_metaval(fake_db, fake_blob)
        data = client.get(f"/api/v1/metaval/{oid}").json()
        for org in data["organisms"]:
            assert "igv_key" not in org

    async def test_verification_data_exposes_availability(
        self, client, fake_db, fake_blob
    ):
        oid, _ = await insert_metaval(fake_db, fake_blob, with_reads=True)
        data = client.get(f"/api/v1/metaval/{oid}").json()
        assert data["verification_data"]["available"] is True
        assert data["verification_data"]["count"] == 20
        assert data["verification_data"]["avg_length"] == 150.0

    async def test_unknown_id_returns_404(self, client, fake_db):
        resp = client.get(f"/api/v1/metaval/{ObjectId()}")
        assert resp.status_code == 404

    async def test_invalid_id_returns_422(self, client, fake_db):
        resp = client.get("/api/v1/metaval/not-an-objectid")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /metaval/{metaval_id}/igv/{organism_name}
# ---------------------------------------------------------------------------


class TestGetIgv:
    async def test_serves_igv_html(self, client, fake_db, fake_blob):
        oid, _ = await insert_metaval(fake_db, fake_blob, with_igv=True)
        resp = client.get(f"/api/v1/metaval/{oid}/igv/Shigella-virus-Moo19")
        assert resp.status_code == 200
        assert "<html>" in resp.text

    async def test_unknown_organism_returns_404(self, client, fake_db, fake_blob):
        oid, _ = await insert_metaval(fake_db, fake_blob)
        resp = client.get(f"/api/v1/metaval/{oid}/igv/Unknown-organism")
        assert resp.status_code == 404

    async def test_unknown_metaval_id_returns_404(self, client, fake_db):
        resp = client.get(f"/api/v1/metaval/{ObjectId()}/igv/Shigella-virus-Moo19")
        assert resp.status_code == 404

    async def test_igv_too_large_returns_413(self, client, fake_db, fake_blob):
        oid, _ = await insert_metaval(fake_db, fake_blob, with_igv=False)
        # Insert a too-large organism manually
        await fake_db["metaval_results"].update_one(
            {"_id": oid},
            {
                "$push": {
                    "organisms": {
                        "organism_name": "BigVirus",
                        "igv_key": None,
                        "igv_file_size_bytes": 11 * 1024 * 1024,
                        "igv_too_large": True,
                    }
                }
            },
        )
        resp = client.get(f"/api/v1/metaval/{oid}/igv/BigVirus")
        assert resp.status_code == 413


# ---------------------------------------------------------------------------
# POST /metaval/{metaval_id}/blast
# ---------------------------------------------------------------------------


class TestBlast:
    async def test_missing_reads_returns_404(self, client, fake_db, fake_blob):
        oid, _ = await insert_metaval(fake_db, fake_blob, with_reads=False)
        resp = client.post(f"/api/v1/metaval/{oid}/blast")
        assert resp.status_code == 404

    async def test_unknown_id_returns_404(self, client, fake_db):
        resp = client.post(f"/api/v1/metaval/{ObjectId()}/blast")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /metaval/{metaval_id}/igv — edge cases
# ---------------------------------------------------------------------------


class TestGetIgvEdgeCases:
    async def test_organism_with_no_igv_key_returns_404(
        self, client, fake_db, fake_blob
    ):
        oid, _ = await insert_metaval(fake_db, fake_blob, with_igv=False)
        await fake_db["metaval_results"].update_one(
            {"_id": oid},
            {
                "$push": {
                    "organisms": {
                        "organism_name": "NoKey",
                        "igv_key": None,
                        "igv_file_size_bytes": 100,
                        "igv_too_large": False,
                    }
                }
            },
        )
        resp = client.get(f"/api/v1/metaval/{oid}/igv/NoKey")
        assert resp.status_code == 404
        assert "not available" in resp.json()["detail"]

    async def test_blob_missing_from_store_returns_404(
        self, client, fake_db, fake_blob
    ):
        oid, _ = await insert_metaval(fake_db, fake_blob, with_igv=False)
        await fake_db["metaval_results"].update_one(
            {"_id": oid},
            {
                "$push": {
                    "organisms": {
                        "organism_name": "MissingBlob",
                        "igv_key": "igv/case/SRR001/kraken2/MissingBlob.html",
                        "igv_file_size_bytes": 100,
                        "igv_too_large": False,
                    }
                }
            },
        )
        resp = client.get(f"/api/v1/metaval/{oid}/igv/MissingBlob")
        assert resp.status_code == 404
        assert "not found in storage" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Serialise — sample_id present and organisms non-empty
# ---------------------------------------------------------------------------


class TestSerialiseExtended:
    async def test_sample_id_serialised_as_string(self, client, fake_db, fake_blob):
        oid, sample_oid = await insert_metaval(fake_db, fake_blob)
        resp = client.get(f"/api/v1/metaval/{oid}")
        assert isinstance(resp.json()["sample_id"], str)
        assert resp.json()["sample_id"] == str(sample_oid)

    async def test_serialise_with_organisms_strips_igv_key(
        self, client, fake_db, fake_blob
    ):
        oid, _ = await insert_metaval(fake_db, fake_blob, with_igv=True)
        resp = client.get(f"/api/v1/metaval/{oid}")
        assert resp.status_code == 200
        for org in resp.json().get("organisms", []):
            assert "igv_key" not in org
        assert "available" in resp.json()["verification_data"]
