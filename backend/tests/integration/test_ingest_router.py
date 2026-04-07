# tests/integration/test_ingest_router.py

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.routers.ingest import router
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


def minimal_ingest_payload(**overrides):
    payload = {
        "case_id":            "testcase",
        "order_date":         "2026-01-01",
        "multiqc_path":       "/data/multiqc_data.json",
        "pipeline_info_path": "/data/software_versions.yml",
        "classifiers": [
            {
                "name":     "kraken2",
                "db":       "k2_pluspf",
                "taxpasta": "/data/kraken2.tsv",
                "krona":    None,
            }
        ],
        "samples": [
            {
                "sample_id":   "SRR001",
                "sample_type": "sample",
                "material":    "DNA",
                "columns":     {"kraken2": "SRR001_kraken2"},
            }
        ],
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# POST /ingest
# ---------------------------------------------------------------------------

class TestIngest:

    async def test_successful_ingest_returns_result(self, client, fake_db):
        mock_result = {"case_id": "testcase", "samples_ingested": 1}
        with patch("app.routers.ingest.ingest_case", new=AsyncMock(return_value=mock_result)):
            resp = client.post("/api/v1/ingest", json=minimal_ingest_payload())
        assert resp.status_code == 200
        assert resp.json()["case_id"] == "testcase"

    async def test_file_not_found_returns_404(self, client, fake_db):
        with patch(
            "app.routers.ingest.ingest_case",
            new=AsyncMock(side_effect=FileNotFoundError("File not found"))
        ):
            resp = client.post("/api/v1/ingest", json=minimal_ingest_payload())
        assert resp.status_code == 404

    async def test_value_error_returns_422(self, client, fake_db):
        with patch(
            "app.routers.ingest.ingest_case",
            new=AsyncMock(side_effect=ValueError("Duplicate case"))
        ):
            resp = client.post("/api/v1/ingest", json=minimal_ingest_payload())
        assert resp.status_code == 422

    async def test_unexpected_error_returns_500(self, client, fake_db):
        with patch(
            "app.routers.ingest.ingest_case",
            new=AsyncMock(side_effect=RuntimeError("Something went wrong"))
        ):
            resp = client.post("/api/v1/ingest", json=minimal_ingest_payload())
        assert resp.status_code == 500

    async def test_ingest_clears_alerts_cache(self, client, fake_db):
        from app.routers import alerts
        alerts._cache[14] = {"outbreaks": []}
        mock_result = {"case_id": "testcase", "samples_ingested": 1}
        with patch("app.routers.ingest.ingest_case", new=AsyncMock(return_value=mock_result)):
            resp = client.post("/api/v1/ingest", json=minimal_ingest_payload())
            assert resp.status_code == 200
            assert alerts._cache == {}