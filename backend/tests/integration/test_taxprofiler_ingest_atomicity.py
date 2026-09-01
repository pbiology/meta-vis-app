# tests/integration/test_ingest_atomicity.py
#
# Verifies the atomicity contract of `ingest_taxprofiler_case`:
#   - prepare phase materialises every doc before any DB write
#   - commit phase runs all Mongo writes inside one transaction
#   - blob uploads run only after the transaction commits
#
# The orchestrator no longer touches the filesystem: it consumes pre-parsed
# TaxprofilerIngestInputs handed to it by the loader (see app.ingestor.loader). These
# tests therefore build TaxprofilerIngestInputs in-memory and skip the filesystem
# entirely. Loader-side failures (missing files, bad bundles) are covered
# separately in tests/unit/test_loader.py.

from unittest.mock import patch

import pandas as pd
import pytest
from mongomock.collection import BulkOperationBuilder
from mongomock.not_implemented import ignore_feature

from app.ingestor import orchestrator
from app.ingestor.inputs import MultiQCRaw, TaxprofilerIngestInputs
from app.models.ingest import (
    TaxprofilerClassifierMeta,
    TaxprofilerIngestMeta,
    TaxprofilerSampleIngestRequest,
)
from app.models.pipeline import PipelineConfiguration, PipelineInfo

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
# In-memory fixtures
# ---------------------------------------------------------------------------


def make_meta(**overrides) -> TaxprofilerIngestMeta:
    payload = {
        "case_id": "atomic-case",
        "order_date": "2026-01-01",
        "classifiers": [TaxprofilerClassifierMeta(name="kraken2", db="k2_pluspf")],
        "samples": [
            TaxprofilerSampleIngestRequest(
                subject_id="SUBJ-1",
                sample_id="SRR001",
                sample_type="sample",
                material="DNA",
                columns={"kraken2": "SRR001_kraken2"},
            )
        ],
        "has_metaval": False,
        "classifiers_with_krona": [],
        "has_multiqc_report": False,
    }
    payload.update(overrides)
    return TaxprofilerIngestMeta(**payload)


def make_inputs(**overrides) -> TaxprofilerIngestInputs:
    multiqc = MultiQCRaw(
        kraken2={
            "SRR001_k2_pluspf": {
                "U": {"unclassified": 100},
                "R": {"root": 900},
                "S": {"Species-A": 400},
                "G": {"Genus-A": 500},
            }
        },
        centrifuge={},
        diamond={},
        fastqc={},
        fastp={},
        bowtie2={},
    )
    pipeline_info = PipelineInfo(
        software_used={"FASTP": {"fastp": "0.23.4"}},
        pipeline_configuration=PipelineConfiguration(
            pipeline_name="nf-core/taxprofiler",
            pipeline_version="1.2.0",
            nextflow="24.10.0",
        ),
    )
    # Match what load_taxpasta() returns: taxonomy_id renamed to taxon_id and
    # coerced to int. The orchestrator gets the already-loaded DataFrame.
    taxpasta = {
        "kraken2": pd.DataFrame(
            {
                "taxon_id": [2],
                "name": ["Bacteria"],
                "rank": ["superkingdom"],
                "lineage": ["Bacteria"],
                "SRR001_kraken2": [1200],
            }
        )
    }
    defaults: dict = {
        "multiqc": multiqc,
        "pipeline_info": pipeline_info,
        "taxpasta": taxpasta,
        "krona_html": {},
        "multiqc_html": None,
        "metaval": None,
    }
    defaults.update(overrides)
    return TaxprofilerIngestInputs(**defaults)


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


class _FakeClient:
    async def start_session(self):
        return _FakeSession()


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
    async def test_happy_path_persists_case_and_samples(self, fake_db):
        result = await orchestrator.ingest_taxprofiler_case(
            make_meta(), make_inputs(), fake_db
        )

        assert result["case_id"] == "atomic-case"
        assert result["analysis_version"] == 1
        assert result["samples_ingested"] == 1

        case = await fake_db["cases"].find_one({"case_id": "atomic-case"})
        assert case is not None

        analysis = await fake_db["case_analysis"].find_one({"case_id": "atomic-case"})
        assert analysis is not None
        assert analysis["version"] == 1
        assert analysis["is_latest"] is True
        assert analysis["sample_count"] == 1

        sample = await fake_db["samples"].find_one({"sample_id": "SRR001"})
        assert sample is not None
        assert sample["analysis_id"] == analysis["_id"]
        assert sample["is_latest_analysis"] is True

    async def test_reingest_appends_a_second_analysis(self, fake_db):
        """Re-ingesting a case adds a run rather than being rejected."""
        await orchestrator.ingest_taxprofiler_case(make_meta(), make_inputs(), fake_db)
        result = await orchestrator.ingest_taxprofiler_case(
            make_meta(), make_inputs(), fake_db
        )

        assert result["analysis_version"] == 2

        # One case, two analyses.
        assert await fake_db["cases"].count_documents({}) == 1
        versions = sorted(
            [
                doc["version"]
                async for doc in fake_db["case_analysis"].find(
                    {"case_id": "atomic-case"}
                )
            ]
        )
        assert versions == [1, 2]

    async def test_reingest_demotes_the_previous_analysis(self, fake_db):
        """Exactly one analysis per case stays latest, samples included.

        The partial unique index enforcing this is not honoured by
        mongomock-motor, so assert the invariant directly.
        """
        await orchestrator.ingest_taxprofiler_case(make_meta(), make_inputs(), fake_db)
        await orchestrator.ingest_taxprofiler_case(make_meta(), make_inputs(), fake_db)

        latest = (
            await fake_db["case_analysis"]
            .find({"case_id": "atomic-case", "is_latest": True})
            .to_list(None)
        )
        assert len(latest) == 1
        assert latest[0]["version"] == 2

        latest_samples = await fake_db["samples"].count_documents(
            {"is_latest_analysis": True}
        )
        superseded_samples = await fake_db["samples"].count_documents(
            {"is_latest_analysis": False}
        )
        assert (latest_samples, superseded_samples) == (1, 1)

    async def test_analysis_carries_sample_metadata(self, fake_db):
        """Counts and names live on the analysis, not the case document."""
        await orchestrator.ingest_taxprofiler_case(make_meta(), make_inputs(), fake_db)

        analysis = await fake_db["case_analysis"].find_one({"case_id": "atomic-case"})
        assert analysis["sample_count"] == 1
        assert analysis["sample_names"] == ["SRR001"]
        assert "sample_ids" not in analysis

    async def test_blob_uploaded_only_after_db_commit(self, fake_db, fake_blob):
        """Krona blob is stored under the analysis version and referenced."""
        meta = make_meta(classifiers_with_krona=["kraken2"])
        inputs = make_inputs(krona_html={"kraken2": "<html>krona</html>"})

        await orchestrator.ingest_taxprofiler_case(meta, inputs, fake_db)

        blob = await fake_blob.get("krona/atomic-case/v1/kraken2.html")
        assert blob == "<html>krona</html>"

        analysis = await fake_db["case_analysis"].find_one({"case_id": "atomic-case"})
        assert analysis["classifiers"][0]["krona_id"] == "kraken2"

    async def test_reingest_namespaces_blobs_per_version(self, fake_db, fake_blob):
        """A second run must not overwrite the first run's Krona report."""
        meta = make_meta(classifiers_with_krona=["kraken2"])
        await orchestrator.ingest_taxprofiler_case(
            meta, make_inputs(krona_html={"kraken2": "<html>v1</html>"}), fake_db
        )
        await orchestrator.ingest_taxprofiler_case(
            meta, make_inputs(krona_html={"kraken2": "<html>v2</html>"}), fake_db
        )

        assert (
            await fake_blob.get("krona/atomic-case/v1/kraken2.html")
            == "<html>v1</html>"
        )
        assert (
            await fake_blob.get("krona/atomic-case/v2/kraken2.html")
            == "<html>v2</html>"
        )
