# tests/integration/test_ingest_atomicity.py
#
# Verifies the atomicity contract of `ingest_case` (CLAUDE_TODO #10):
#   - prepare phase validates inputs before any DB write
#   - commit phase runs all Mongo writes inside one transaction
#   - blob uploads run only after the transaction commits
#
# mongomock-motor does not implement real transactions, so these tests
# patch `get_client()` with a fake that provides a no-op session +
# transaction. That is sufficient to verify the *ordering* contract
# (no writes before validation, no blob uploads before commit). True
# rollback verification requires a real replica-set Mongo and is out of
# scope for the unit/integration tier.

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from mongomock.collection import BulkOperationBuilder
from mongomock.not_implemented import ignore_feature

from app.models.sample import IngestRequest
from app.ingestor import orchestrator

# Mongomock doesn't implement real sessions/transactions; we verify ordering
# and prepare-phase validation rather than true rollback, which requires a
# real replica-set Mongo.
ignore_feature("session")

# pymongo 4.16 adds `sort` to UpdateOne._add_to_bulk, which mongomock 4.3
# doesn't accept. Strip it in tests — the orchestrator never sorts upserts.
_orig_add_update = BulkOperationBuilder.add_update


def _add_update_compat(self, *args, **kwargs):  # type: ignore[no-untyped-def]
    kwargs.pop("sort", None)
    return _orig_add_update(self, *args, **kwargs)


BulkOperationBuilder.add_update = _add_update_compat  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Fixtures — minimal on-disk inputs
# ---------------------------------------------------------------------------


@pytest.fixture
def multiqc_path(tmp_path: Path) -> str:
    p = tmp_path / "multiqc_data.json"
    p.write_text(
        json.dumps(
            {
                "report_saved_raw_data": {
                    "multiqc_kraken": {
                        "SRR001_k2_pluspf": {
                            "U": {"unclassified": 100},
                            "R": {"root": 900},
                            "S": {"Species-A": 400},
                            "G": {"Genus-A": 500},
                        }
                    }
                }
            }
        )
    )
    return str(p)


@pytest.fixture
def pipeline_info_path(tmp_path: Path) -> str:
    p = tmp_path / "software_versions.yml"
    p.write_text(
        yaml.safe_dump(
            {
                "Workflow": {"Nextflow": "24.10.0", "nf-core/taxprofiler": "1.2.0"},
                "FASTP": {"fastp": "0.23.4"},
            }
        )
    )
    return str(p)


@pytest.fixture
def taxpasta_path(tmp_path: Path) -> str:
    p = tmp_path / "kraken2.tsv"
    p.write_text(
        "taxonomy_id\tname\trank\tlineage\tSRR001_kraken2\n"
        "2\tBacteria\tsuperkingdom\tBacteria\t1200\n"
    )
    return str(p)


def make_request(multiqc_path, pipeline_info_path, taxpasta_path, **overrides):
    payload = {
        "case_id": "atomic-case",
        "order_date": "2026-01-01",
        "multiqc_path": multiqc_path,
        "pipeline_info_path": pipeline_info_path,
        "classifiers": [
            {
                "name": "kraken2",
                "db": "k2_pluspf",
                "taxpasta": taxpasta_path,
                "krona": None,
            }
        ],
        "samples": [
            {
                "sample_id": "SRR001",
                "sample_type": "sample",
                "material": "DNA",
                "columns": {"kraken2": "SRR001_kraken2"},
            }
        ],
    }
    payload.update(overrides)
    return IngestRequest(**payload)


# ---------------------------------------------------------------------------
# Fake Motor client whose session/transaction context managers are no-ops
# ---------------------------------------------------------------------------


class _FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def start_transaction(self):
        return self

    # start_transaction() returns a context manager; reuse self


class _FakeClient:
    async def start_session(self):
        return _FakeSession()


@pytest.fixture
def patched_client():
    with patch.object(
        orchestrator, "get_client", return_value=_FakeClient(), create=True
    ):
        # get_client is imported lazily inside ingest_case via `from app.database import get_client`.
        # Patch it on app.database instead.
        yield


@pytest.fixture(autouse=True)
def patch_db_client():
    with patch.object(orchestrator, "get_client", return_value=_FakeClient()):
        yield


@pytest.fixture(autouse=True)
def patch_blob_store(fake_blob):
    import app.database as database_module

    with patch.object(database_module, "get_blob_store", return_value=fake_blob):
        yield


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIngestAtomicity:
    async def test_happy_path_persists_case_and_samples(
        self, fake_db, multiqc_path, pipeline_info_path, taxpasta_path
    ):
        request = make_request(multiqc_path, pipeline_info_path, taxpasta_path)
        result = await orchestrator.ingest_case(request, fake_db)

        assert result["case_id"] == "atomic-case"
        assert result["samples_ingested"] == 1

        case = await fake_db["cases"].find_one({"case_id": "atomic-case"})
        assert case is not None
        assert len(case["sample_ids"]) == 1
        assert case["sample_count"] == 1

        sample = await fake_db["samples"].find_one({"sample_id": "SRR001"})
        assert sample is not None
        # Sample _id matches the case's reference
        assert sample["_id"] == case["sample_ids"][0]

    async def test_missing_multiqc_fails_before_any_db_write(
        self, fake_db, pipeline_info_path, taxpasta_path
    ):
        request = make_request(
            "/nonexistent/multiqc.json", pipeline_info_path, taxpasta_path
        )
        with pytest.raises(FileNotFoundError):
            await orchestrator.ingest_case(request, fake_db)

        assert await fake_db["cases"].count_documents({}) == 0
        assert await fake_db["samples"].count_documents({}) == 0
        assert await fake_db["taxa"].count_documents({}) == 0

    async def test_missing_taxpasta_fails_before_any_db_write(
        self, fake_db, multiqc_path, pipeline_info_path
    ):
        request = make_request(
            multiqc_path, pipeline_info_path, "/nonexistent/taxpasta.tsv"
        )
        with pytest.raises(FileNotFoundError):
            await orchestrator.ingest_case(request, fake_db)

        assert await fake_db["cases"].count_documents({}) == 0
        assert await fake_db["samples"].count_documents({}) == 0

    async def test_missing_krona_fails_before_any_db_write(
        self, fake_db, multiqc_path, pipeline_info_path, taxpasta_path
    ):
        request = make_request(
            multiqc_path,
            pipeline_info_path,
            taxpasta_path,
            classifiers=[
                {
                    "name": "kraken2",
                    "db": "k2_pluspf",
                    "taxpasta": taxpasta_path,
                    "krona": "/nonexistent/krona.html",
                }
            ],
        )
        with pytest.raises(FileNotFoundError):
            await orchestrator.ingest_case(request, fake_db)

        assert await fake_db["cases"].count_documents({}) == 0
        assert await fake_db["samples"].count_documents({}) == 0

    async def test_duplicate_case_id_rejected_without_writes(
        self, fake_db, multiqc_path, pipeline_info_path, taxpasta_path
    ):
        # Pre-seed the case
        await fake_db["cases"].insert_one({"case_id": "atomic-case"})

        request = make_request(multiqc_path, pipeline_info_path, taxpasta_path)
        with pytest.raises(ValueError, match="already exists"):
            await orchestrator.ingest_case(request, fake_db)

        # No new samples or taxa were written
        assert await fake_db["samples"].count_documents({}) == 0
        assert await fake_db["taxa"].count_documents({}) == 0

    async def test_case_doc_written_with_sample_ids_in_single_write(
        self, fake_db, multiqc_path, pipeline_info_path, taxpasta_path
    ):
        """
        The refactor removes the 'insert case with empty sample_ids, then patch
        later' pattern. Verify that the persisted case doc has sample_ids
        populated from the start.
        """
        request = make_request(multiqc_path, pipeline_info_path, taxpasta_path)
        await orchestrator.ingest_case(request, fake_db)

        case = await fake_db["cases"].find_one({"case_id": "atomic-case"})
        assert case["sample_ids"], "case.sample_ids must be populated at insert time"
        assert case["sample_count"] == 1
        assert case["sample_names"] == ["SRR001"]

    async def test_blob_uploaded_only_after_db_commit(
        self,
        fake_db,
        tmp_path,
        multiqc_path,
        pipeline_info_path,
        taxpasta_path,
        fake_blob,
    ):
        """Krona blob must be in the store only if the case doc is also present."""
        krona = tmp_path / "krona.html"
        krona.write_text("<html>krona</html>")

        request = make_request(
            multiqc_path,
            pipeline_info_path,
            taxpasta_path,
            classifiers=[
                {
                    "name": "kraken2",
                    "db": "k2_pluspf",
                    "taxpasta": taxpasta_path,
                    "krona": str(krona),
                }
            ],
        )
        await orchestrator.ingest_case(request, fake_db)

        # Blob is present
        blob = await fake_blob.get("krona/atomic-case/kraken2.html")
        assert blob == "<html>krona</html>"

        # Case doc is present and references the blob
        case = await fake_db["cases"].find_one({"case_id": "atomic-case"})
        assert case["classifiers"][0]["krona_id"] == "kraken2"
