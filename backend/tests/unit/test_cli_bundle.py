# tests/unit/test_cli_bundle.py
#
# Round-trip test for the CLI bundle builder: a bundle built by ingest.py
# (repo root) must extract cleanly via app.ingestor.loader and produce inputs
# the orchestrator can consume.

import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from app.ingestor.loader import load_taxprofiler_bundle


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


async def test_cli_bundle_round_trips_through_loader(tmp_path, cli):
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
                "nucleic_acid": "DNA",
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


class TestDeprecatedMaterialAlias:
    """The nucleic_acid field was renamed from material. Saved clinic ingest
    command lines still say material=, so the CLI accepts it — loudly, and
    never when it would have to guess between two conflicting values."""

    def test_material_is_rewritten_to_nucleic_acid_with_a_warning(self, cli, capsys):
        parts = {"sample_id": "S1", "material": "DNA"}

        cli._resolve_nucleic_acid(parts)

        assert parts == {"sample_id": "S1", "nucleic_acid": "DNA"}
        assert "deprecated" in capsys.readouterr().err

    def test_nucleic_acid_alone_is_left_untouched(self, cli, capsys):
        parts = {"sample_id": "S1", "nucleic_acid": "RNA"}

        cli._resolve_nucleic_acid(parts)

        assert parts == {"sample_id": "S1", "nucleic_acid": "RNA"}
        assert capsys.readouterr().err == ""

    def test_setting_both_keys_exits_rather_than_picking_one(self, cli):
        parts = {"sample_id": "S1", "material": "DNA", "nucleic_acid": "RNA"}

        with pytest.raises(SystemExit) as exc:
            cli._resolve_nucleic_acid(parts)

        assert exc.value.code == 1


class TestControlOrderDate:
    """A control is prepared once and sequenced alongside every case in its
    run, so the CLI lets it declare its own order date. The token is validated
    here rather than server-side: a malformed date should fail before anything
    is uploaded, and a dropped one would silently reintroduce the case's date."""

    def test_valid_date_is_normalised(self, cli):
        parts = {"sample_id": "NTC-260305-DNA", "order_date": "2026-03-05"}

        assert cli._parse_sample_order_date(parts, "NTC-260305-DNA") == "2026-03-05"

    def test_absent_token_is_none(self, cli):
        assert cli._parse_sample_order_date({}, "NTC-260305-DNA") is None

    def test_malformed_date_exits(self, cli):
        parts = {"order_date": "05/03/2026"}

        with pytest.raises(SystemExit) as exc:
            cli._parse_sample_order_date(parts, "NTC-260305-DNA")

        assert exc.value.code == 1

    def test_impossible_date_exits(self, cli):
        parts = {"order_date": "2026-02-30"}

        with pytest.raises(SystemExit) as exc:
            cli._parse_sample_order_date(parts, "NTC-260305-DNA")

        assert exc.value.code == 1

    def test_parse_sample_carries_the_token(self, cli):
        parsed = cli.parse_sample(
            "sample_id=NTC-260305-DNA type=negative_ctrl nucleic_acid=DNA "
            "order_date=2026-03-05 column_kraken2=NTC-260305-DNA_k2_pluspf",
            ["kraken2"],
        )

        assert parsed["order_date"] == "2026-03-05"

    def test_parse_trana_sample_carries_the_token(self, cli, tmp_path):
        abundance = tmp_path / "abundance.tsv"
        abundance.write_text("tax_id\tabundance\n")

        parsed = cli.parse_trana_sample(
            "sample_id=16SNEGABC123 type=negative_ctrl nucleic_acid=DNA "
            f"order_date=2026-03-05 abundance_path={abundance}"
        )

        assert parsed["order_date"] == "2026-03-05"


async def test_control_order_date_survives_the_bundle(tmp_path, cli):
    """The control's date must reach the manifest the backend validates. The
    taxprofiler builder passes samples through verbatim, but the trana builder
    rebuilds each manifest entry field by field — where a new key is dropped
    unless it is listed."""
    src = _write_minimal_inputs(tmp_path)
    bundle = tmp_path / "bundle.tar.gz"
    extracted = tmp_path / "extracted"
    extracted.mkdir()

    cli.build_taxprofiler_bundle(
        bundle,
        case_id="control-own-date",
        ticket_id=None,
        order_date="2026-09-03",
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
                "nucleic_acid": "DNA",
                "sample_source": "N/A",
                "order_date": None,
                "columns": {"kraken2": "S1_kraken2"},
            },
            {
                "subject_id": None,
                "subject_sex": "unknown",
                "sample_id": "NTC-260305-DNA",
                "sample_type": "negative_ctrl",
                "nucleic_acid": "DNA",
                "sample_source": "N/A",
                "order_date": "2026-03-05",
                "columns": {"kraken2": "S1_kraken2"},
            },
        ],
        analysis_type="shotgun",
        sequencing_platform="illumina",
    )

    meta, _ = await load_taxprofiler_bundle(bundle, extracted)

    by_id = {s.sample_id: s for s in meta.samples}
    assert by_id["NTC-260305-DNA"].order_date == date(2026, 3, 5)
    # The clinical sample keeps inheriting the case's date.
    assert by_id["S1"].order_date is None
    assert meta.order_date == date(2026, 9, 3)
