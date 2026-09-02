# tests/integration/test_analysis_version_isolation.py
#
# A differential audit: one case with two analyses whose data genuinely
# differs, walked endpoint by endpoint to prove each version-scoped route
# returns *its own* run's data.
#
# This exists because the refactor produced the same bug five times — a
# run-scoped operation silently resolving to the latest analysis. That failure
# is invisible in the UI, because the wrong run's data is always plausible.
# Fixtures built by re-ingesting the same bundle cannot catch it: the runs come
# out byte-identical apart from the order date, so v1 and v2 are
# indistinguishable by construction. Every field below is therefore made to
# differ on purpose.

import pytest
from fastapi.testclient import TestClient

from app.routers.analyses import router as analyses_router
from app.routers.cases import router as cases_router
from tests.helpers import insert_case, insert_sample, make_test_app

CASE = "VERSIONED-1"


@pytest.fixture
def app(fake_db, fake_blob):
    return make_test_app([cases_router, analyses_router], fake_db, fake_blob)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
async def two_analyses(fake_db, fake_blob):
    """One case, two analyses, differing in every field a view can read."""
    v1 = await insert_case(
        fake_db,
        CASE,
        version=1,
        is_latest=False,
        reviewed=True,
        reviewed_by="alice",
        order_date="2026-05-01",
        analysis_type="shotgun",
        sequencing_platform="illumina",
        has_krona=True,
        has_multiqc=True,
        sample_count=1,
        classifiers=[{"name": "kraken2", "db": "pluspf-2024", "krona_id": "kraken2"}],
        report_selections={"S1": [1280]},
        metaval_pipeline_info=None,
    )
    v2 = await insert_case(
        fake_db,
        CASE,
        version=2,
        is_latest=True,
        reviewed=False,
        order_date="2026-08-01",
        analysis_type="shotgun",
        sequencing_platform="nanopore",
        has_krona=True,
        has_multiqc=True,
        sample_count=1,
        classifiers=[{"name": "kraken2", "db": "pluspf-2025", "krona_id": "kraken2"}],
        report_selections={},
        metaval_pipeline_info={"software_used": {}, "pipeline_configuration": {}},
    )

    # Same sample name in both runs, with different read counts — the case that
    # makes "which analysis am I reading?" observable.
    await insert_sample(
        fake_db,
        v1,
        CASE,
        "S1",
        is_latest_analysis=False,
        taxprofiler={"classifiers": {"kraken2": {"num_species": 11}}},
        all_taxon_ids=[1280],
    )
    await insert_sample(
        fake_db,
        v2,
        CASE,
        "S1",
        is_latest_analysis=True,
        taxprofiler={"classifiers": {"kraken2": {"num_species": 22}}},
        all_taxon_ids=[1280, 573],
    )

    await fake_blob.put(f"krona/{CASE}/v1/kraken2.html", "<html>krona v1</html>")
    await fake_blob.put(f"krona/{CASE}/v2/kraken2.html", "<html>krona v2</html>")
    await fake_blob.put(f"multiqc/{CASE}/v1/report.html", "<html>multiqc v1</html>")
    await fake_blob.put(f"multiqc/{CASE}/v2/report.html", "<html>multiqc v2</html>")
    return {"v1": v1, "v2": v2}


class TestVersionIsolation:
    async def test_detail_returns_the_requested_run(self, client, two_analyses):
        v1 = client.get(f"/api/v1/cases/{CASE}/analyses/1").json()
        v2 = client.get(f"/api/v1/cases/{CASE}/analyses/2").json()

        assert v1["analysis"]["version"] == 1
        assert v2["analysis"]["version"] == 2
        assert v1["analysis"]["classifiers"][0]["db"] == "pluspf-2024"
        assert v2["analysis"]["classifiers"][0]["db"] == "pluspf-2025"
        assert v1["analysis"]["sequencing_platform"] == "illumina"
        assert v2["analysis"]["sequencing_platform"] == "nanopore"
        # Identity is shared; only the run differs.
        assert v1["case"]["case_id"] == v2["case"]["case_id"] == CASE

    async def test_bare_route_resolves_to_latest(self, client, two_analyses):
        body = client.get(f"/api/v1/cases/{CASE}").json()
        assert body["analysis"]["version"] == 2
        assert body["analysis"]["is_latest"] is True

    async def test_review_state_is_per_run(self, client, two_analyses):
        v1 = client.get(f"/api/v1/cases/{CASE}/analyses/1").json()
        v2 = client.get(f"/api/v1/cases/{CASE}/analyses/2").json()
        assert v1["analysis"]["review"]["reviewed"] is True
        assert v1["analysis"]["review"]["reviewed_by"] == "alice"
        assert v2["analysis"]["review"]["reviewed"] is False

    async def test_samples_come_from_the_requested_run(self, client, two_analyses):
        v1 = client.get(f"/api/v1/cases/{CASE}/analyses/1/samples").json()
        v2 = client.get(f"/api/v1/cases/{CASE}/analyses/2/samples").json()

        # Same sample_id in both runs — only the QC numbers tell them apart.
        assert [s["sample_id"] for s in v1] == ["S1"]
        assert [s["sample_id"] for s in v2] == ["S1"]
        assert v1[0]["taxprofiler"]["classifiers"]["kraken2"]["num_species"] == 11
        assert v2[0]["taxprofiler"]["classifiers"]["kraken2"]["num_species"] == 22
        assert v1[0]["_id"] != v2[0]["_id"]

    async def test_krona_serves_the_requested_run(self, client, two_analyses):
        assert "krona v1" in client.get(f"/api/v1/cases/{CASE}/analyses/1/krona").text
        assert "krona v2" in client.get(f"/api/v1/cases/{CASE}/analyses/2/krona").text
        # Bare route follows the latest.
        assert "krona v2" in client.get(f"/api/v1/cases/{CASE}/krona").text

    async def test_multiqc_serves_the_requested_run(self, client, two_analyses):
        assert (
            "multiqc v1" in client.get(f"/api/v1/cases/{CASE}/analyses/1/multiqc").text
        )
        assert (
            "multiqc v2" in client.get(f"/api/v1/cases/{CASE}/analyses/2/multiqc").text
        )
        assert "multiqc v2" in client.get(f"/api/v1/cases/{CASE}/multiqc").text

    async def test_report_draft_is_per_run(self, client, two_analyses):
        v1 = client.get(f"/api/v1/cases/{CASE}/analyses/1").json()
        v2 = client.get(f"/api/v1/cases/{CASE}/analyses/2").json()
        assert v1["analysis"]["report_selections"] == {"S1": [1280]}
        assert v2["analysis"]["report_selections"] == {}

    async def test_reviewing_one_run_leaves_the_other_untouched(
        self, client, two_analyses
    ):
        resp = client.patch(
            f"/api/v1/cases/{CASE}/analyses/2/review", json={"notes": None}
        )
        assert resp.status_code == 200

        v1 = client.get(f"/api/v1/cases/{CASE}/analyses/1").json()
        v2 = client.get(f"/api/v1/cases/{CASE}/analyses/2").json()
        assert v2["analysis"]["review"]["reviewed"] is True
        # v1's record must keep its original reviewer, not be rewritten.
        assert v1["analysis"]["review"]["reviewed_by"] == "alice"

    async def test_report_update_targets_only_the_named_run(self, client, two_analyses):
        resp = client.patch(
            f"/api/v1/cases/{CASE}/analyses/2/report",
            json={"selections": {"S1": [573]}},
        )
        assert resp.status_code == 200

        v1 = client.get(f"/api/v1/cases/{CASE}/analyses/1").json()
        v2 = client.get(f"/api/v1/cases/{CASE}/analyses/2").json()
        assert v2["analysis"]["report_selections"] == {"S1": [573]}
        assert v1["analysis"]["report_selections"] == {"S1": [1280]}

    async def test_case_list_shows_one_row_with_the_latest_run(
        self, client, two_analyses
    ):
        body = client.get("/api/v1/cases").json()
        rows = [r for r in body["items"] if r["case"]["case_id"] == CASE]
        assert len(rows) == 1
        assert rows[0]["latest"]["version"] == 2
        assert [a["version"] for a in rows[0]["superseded_analyses"]] == [1]

    async def test_notes_are_shared_across_runs(self, client, two_analyses):
        client.post(f"/api/v1/cases/{CASE}/notes", json={"text": "seen from both"})

        v1 = client.get(f"/api/v1/cases/{CASE}/analyses/1").json()
        v2 = client.get(f"/api/v1/cases/{CASE}/analyses/2").json()
        assert [n["text"] for n in v1["case"]["notes"]] == ["seen from both"]
        assert [n["text"] for n in v2["case"]["notes"]] == ["seen from both"]

    async def test_carry_forward_reads_the_named_source(self, client, two_analyses):
        resp = client.post(
            f"/api/v1/cases/{CASE}/analyses/2/report/carry-forward",
            params={"from_version": 1},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["from_version"] == 1
        # 1280 exists in v2's sample, so it carries; nothing else was picked.
        assert body["applied"] == {"S1": [1280]}
        assert body["dropped"] == []
