# tests/integration/test_cases_krona.py

import pytest
from fastapi.testclient import TestClient

from app.routers.analyses import router
from tests.helpers import insert_case as seed_case
from tests.helpers import make_test_app


@pytest.fixture
def app(fake_db, fake_blob):
    return make_test_app(router, fake_db, fake_blob)


@pytest.fixture
def client(app):
    return TestClient(app)


async def insert_case(db, case_id="testcase", has_krona=True):
    return await seed_case(db, case_id, has_krona=has_krona)


# ---------------------------------------------------------------------------
# GET /cases/{case_id}/krona
# ---------------------------------------------------------------------------


class TestGetCaseKrona:
    async def test_serves_krona_html(self, client, fake_db, fake_blob):
        await insert_case(fake_db, "testcase")
        await fake_blob.put("krona/testcase/v1/kraken2.html", "<html>krona</html>")
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
        await insert_case(fake_db, "testcase")
        await fake_blob.put("krona/testcase/v1/kraken2.html", "<html>krona</html>")
        resp = client.get("/api/v1/cases/testcase/krona")
        assert resp.status_code == 200
