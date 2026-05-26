# tests/unit/test_cli_bundle.py
#
# Round-trip test for the CLI bundle builder: a bundle built by ingest.py
# (repo root) must extract cleanly via app.ingestor.loader and produce inputs
# the orchestrator can consume.

import importlib.util
import json
import sys
from pathlib import Path

import yaml

from app.ingestor.loader import load_taxprofiler_bundle


def _load_cli_module():
    """Load the repo-root ingest.py as a module without executing main()."""
    # backend/tests/unit/test_cli_bundle.py -> repo root is parents[3]
    repo_root = Path(__file__).resolve().parents[3]
    cli_path = repo_root / "ingest.py"
    spec = importlib.util.spec_from_file_location("ingest_cli", cli_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["ingest_cli"] = module
    spec.loader.exec_module(module)
    return module


def _write_minimal_inputs(tmp_path: Path) -> dict[str, str]:
    multiqc = tmp_path / "multiqc_data.json"
    multiqc.write_text(
        json.dumps(
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
        )
    )
    pipeline_info = tmp_path / "software_versions.yml"
    pipeline_info.write_text(
        yaml.safe_dump(
            {
                "Workflow": {"Nextflow": "24.10.0", "nf-core/taxprofiler": "1.2.0"},
                "FASTP": {"fastp": "0.23.4"},
            }
        )
    )
    taxpasta = tmp_path / "kraken2.tsv"
    taxpasta.write_text(
        "taxonomy_id\tname\trank\tlineage\tS1_kraken2\n"
        "2\tBacteria\tsuperkingdom\tBacteria\t1200\n"
    )
    krona = tmp_path / "kraken2.html"
    krona.write_text("<html>krona</html>")
    return {
        "multiqc": str(multiqc),
        "pipeline_info": str(pipeline_info),
        "taxpasta": str(taxpasta),
        "krona": str(krona),
    }


async def test_cli_bundle_round_trips_through_loader(tmp_path):
    cli = _load_cli_module()
    src = _write_minimal_inputs(tmp_path)
    bundle = tmp_path / "bundle.tar.gz"
    extracted = tmp_path / "extracted"
    extracted.mkdir()

    cli.build_taxprofiler_bundle(
        bundle,
        case_id="cli-roundtrip",
        ticket_id=None,
        order_date=None,
        multiqc_path=src["multiqc"],
        multiqc_report_path=None,
        pipeline_info_path=src["pipeline_info"],
        metaval_dir=None,
        classifiers=[
            {
                "name": "kraken2",
                "db": "k2_pluspf",
                "taxpasta": src["taxpasta"],
                "krona": src["krona"],
            }
        ],
        samples=[
            {
                "subject_id": "SUBJ-1",
                "subject_sex": "unknown",
                "sample_id": "S1",
                "sample_type": "sample",
                "material": "DNA",
                "sample_source": "N/A",
                "columns": {"kraken2": "S1_kraken2"},
            }
        ],
        analysis_type="shotgun",
        sequencing_platform="illumina",
    )

    meta, inputs = await load_taxprofiler_bundle(bundle, extracted)

    assert meta.case_id == "cli-roundtrip"
    assert meta.classifiers_with_krona == ["kraken2"]
    assert "kraken2" in inputs.krona_html
    assert "kraken2" in inputs.taxpasta
    assert inputs.metaval is None
    assert inputs.multiqc_html is None
