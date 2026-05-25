# tests/unit/test_loader.py
#
# Loader-side bundle tests. We build tar.gz files programmatically (no
# dependency on backend/test-data/) and assert:
#   - happy-path extraction produces correct TaxprofilerIngestMeta + TaxprofilerIngestInputs
#   - unsafe member names are rejected (absolute, .., symlink)
#   - missing manifest, missing referenced files, and manifest/bundle
#     mismatches produce BundleError (HTTP 400 in the router)
#   - the compressed size cap raises BundleTooLargeError
#
# These tests cover what used to be the "file not found" path of the
# orchestrator: that responsibility now lives in the loader.

import io
import json
import tarfile
from pathlib import Path

import pytest
import yaml

from app.config import settings
from app.ingestor.loader import (
    BundleError,
    BundleTooLargeError,
    load_taxprofiler_bundle,
)


def _add_bytes(tar: tarfile.TarFile, arcname: str, data: bytes) -> None:
    info = tarfile.TarInfo(name=arcname)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def _minimal_manifest(**overrides):
    base = {
        "case_id": "loader-case",
        "classifiers": [{"name": "kraken2", "db": "k2_pluspf"}],
        "samples": [
            {
                "sample_id": "S1",
                "sample_type": "sample",
                "material": "DNA",
                "columns": {"kraken2": "S1_kraken2"},
            }
        ],
        "has_metaval": False,
        "classifiers_with_krona": [],
        "has_multiqc_report": False,
    }
    base.update(overrides)
    return base


def _multiqc_payload() -> bytes:
    return json.dumps(
        {
            "report_saved_raw_data": {
                "multiqc_kraken": {
                    "S1_k2_pluspf": {
                        "U": {"unclassified": 100},
                        "R": {"root": 900},
                        "S": {"Species-A": 400},
                    }
                }
            }
        }
    ).encode("utf-8")


def _pipeline_info_payload() -> bytes:
    return yaml.safe_dump(
        {
            "Workflow": {"Nextflow": "24.10.0", "nf-core/taxprofiler": "1.2.0"},
            "FASTP": {"fastp": "0.23.4"},
        }
    ).encode("utf-8")


def _taxpasta_payload() -> bytes:
    return (
        b"taxonomy_id\tname\trank\tlineage\tS1_kraken2\n"
        b"2\tBacteria\tsuperkingdom\tBacteria\t1200\n"
    )


def _build_bundle(tar_path: Path, manifest: dict, *, extras=None) -> None:
    extras = extras or {}
    with tarfile.open(tar_path, mode="w:gz") as tar:
        _add_bytes(tar, "manifest.json", json.dumps(manifest).encode("utf-8"))
        _add_bytes(tar, "multiqc/multiqc_data.json", _multiqc_payload())
        _add_bytes(tar, "pipeline_info/software_versions.yml", _pipeline_info_payload())
        _add_bytes(tar, "classifiers/kraken2/taxpasta/kraken2.tsv", _taxpasta_payload())
        for arc, data in extras.items():
            _add_bytes(tar, arc, data)


class TestLoaderHappyPath:
    async def test_minimal_bundle_loads(self, tmp_path):
        bundle = tmp_path / "bundle.tar.gz"
        dest = tmp_path / "extracted"
        dest.mkdir()
        _build_bundle(bundle, _minimal_manifest())

        meta, inputs = await load_taxprofiler_bundle(bundle, dest)

        assert meta.case_id == "loader-case"
        assert [c.name for c in meta.classifiers] == ["kraken2"]
        assert inputs.multiqc_html is None
        assert inputs.metaval is None
        assert "kraken2" in inputs.taxpasta
        assert inputs.krona_html == {}

    async def test_krona_and_multiqc_html_loaded(self, tmp_path):
        bundle = tmp_path / "bundle.tar.gz"
        dest = tmp_path / "extracted"
        dest.mkdir()
        manifest = _minimal_manifest(
            classifiers_with_krona=["kraken2"], has_multiqc_report=True
        )
        _build_bundle(
            bundle,
            manifest,
            extras={
                "classifiers/kraken2/krona/krona.html": b"<html>krona</html>",
                "multiqc_report/multiqc_report.html": b"<html>report</html>",
            },
        )

        _meta, inputs = await load_taxprofiler_bundle(bundle, dest)

        assert inputs.krona_html == {"kraken2": "<html>krona</html>"}
        assert inputs.multiqc_html == "<html>report</html>"


class TestLoaderSafety:
    async def test_absolute_member_rejected(self, tmp_path):
        bundle = tmp_path / "bundle.tar.gz"
        dest = tmp_path / "extracted"
        dest.mkdir()
        with tarfile.open(bundle, mode="w:gz") as tar:
            _add_bytes(tar, "/etc/passwd", b"x")

        with pytest.raises(BundleError):
            await load_taxprofiler_bundle(bundle, dest)

    async def test_parent_traversal_rejected(self, tmp_path):
        bundle = tmp_path / "bundle.tar.gz"
        dest = tmp_path / "extracted"
        dest.mkdir()
        with tarfile.open(bundle, mode="w:gz") as tar:
            _add_bytes(tar, "../escape.txt", b"x")

        with pytest.raises(BundleError):
            await load_taxprofiler_bundle(bundle, dest)

    async def test_symlink_rejected(self, tmp_path):
        bundle = tmp_path / "bundle.tar.gz"
        dest = tmp_path / "extracted"
        dest.mkdir()
        with tarfile.open(bundle, mode="w:gz") as tar:
            info = tarfile.TarInfo(name="link")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)

        with pytest.raises(BundleError):
            await load_taxprofiler_bundle(bundle, dest)

    async def test_missing_manifest_rejected(self, tmp_path):
        bundle = tmp_path / "bundle.tar.gz"
        dest = tmp_path / "extracted"
        dest.mkdir()
        with tarfile.open(bundle, mode="w:gz") as tar:
            _add_bytes(tar, "something.txt", b"hi")

        with pytest.raises(BundleError, match="manifest.json"):
            await load_taxprofiler_bundle(bundle, dest)

    async def test_manifest_says_metaval_but_subtree_missing(self, tmp_path):
        bundle = tmp_path / "bundle.tar.gz"
        dest = tmp_path / "extracted"
        dest.mkdir()
        _build_bundle(bundle, _minimal_manifest(has_metaval=True))

        with pytest.raises(BundleError, match="has_metaval"):
            await load_taxprofiler_bundle(bundle, dest)

    async def test_missing_taxpasta_for_classifier_rejected(self, tmp_path):
        bundle = tmp_path / "bundle.tar.gz"
        dest = tmp_path / "extracted"
        dest.mkdir()
        with tarfile.open(bundle, mode="w:gz") as tar:
            _add_bytes(
                tar,
                "manifest.json",
                json.dumps(_minimal_manifest()).encode("utf-8"),
            )
            _add_bytes(tar, "multiqc/multiqc_data.json", _multiqc_payload())
            _add_bytes(
                tar, "pipeline_info/software_versions.yml", _pipeline_info_payload()
            )
            # taxpasta missing on purpose

        with pytest.raises(BundleError, match="taxpasta"):
            await load_taxprofiler_bundle(bundle, dest)

    async def test_uncompressed_cap_enforced(self, tmp_path, monkeypatch):
        bundle = tmp_path / "bundle.tar.gz"
        dest = tmp_path / "extracted"
        dest.mkdir()
        monkeypatch.setattr(settings, "ingest_upload_max_uncompressed_bytes", 1024)
        # Build a bundle whose taxpasta is bigger than the cap.
        big = b"x" * 8192
        with tarfile.open(bundle, mode="w:gz") as tar:
            _add_bytes(
                tar,
                "manifest.json",
                json.dumps(_minimal_manifest()).encode("utf-8"),
            )
            _add_bytes(tar, "multiqc/multiqc_data.json", _multiqc_payload())
            _add_bytes(
                tar, "pipeline_info/software_versions.yml", _pipeline_info_payload()
            )
            _add_bytes(tar, "classifiers/kraken2/taxpasta/kraken2.tsv", big)

        with pytest.raises(BundleTooLargeError):
            await load_taxprofiler_bundle(bundle, dest)
