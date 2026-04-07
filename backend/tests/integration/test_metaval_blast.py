# tests/integration/test_cases_krona.py

import pytest
from bson import ObjectId
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.routers.cases import router
from tests.helpers import make_test_app


@pytest.fixture
def app(fake_db, fake_blob):
    return make_test_app(router, fake_db, fake_blob)


@pytest.fixture
def client(app):
    return TestClient(app)


async def insert_case(db, case_id="testcase", has_krona=True):
    result = await db["cases"].insert_one(
        {
            "case_id": case_id,
            "ingested_at": datetime.now(timezone.utc),
            "has_krona": has_krona,
            "classifiers": [],
            "review": {"reviewed": False},
            "notes": [],
        }
    )
    return result.inserted_id


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/krona
# ---------------------------------------------------------------------------


class TestGetCaseKrona:
    async def test_serves_krona_html(self, client, fake_db, fake_blob):
        oid = await insert_case(fake_db, "testcase")
        await fake_blob.put(f"krona/{oid}/kraken2.html", "<html>krona</html>")
        resp = client.get("/api/v1/cases/testcase/krona?classifier=kraken2")
        assert resp.status_code == 200
        assert "<html>" in resp.text

    async def test_unknown_case_returns_404(self, client, fake_db):
        resp = client.get("/api/v1/cases/nonexistent/krona")
        assert resp.status_code == 404

    async def test_missing_blob_returns_404(self, client, fake_db, fake_blob):
        await insert_case(fake_db, "testcase")
        resp = client.get("/api/v1/cases/testcase/krona?classifier=kraken2")
        assert resp.status_code == 404

    async def test_default_classifier_is_kraken2(self, client, fake_db, fake_blob):
        oid = await insert_case(fake_db, "testcase")
        await fake_blob.put(f"krona/{oid}/kraken2.html", "<html>krona</html>")
        resp = client.get("/api/v1/cases/testcase/krona")
        assert resp.status_code == 200
