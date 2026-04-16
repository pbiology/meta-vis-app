# tests/unit/test_multiqc_reader.py

import json
import pytest
from app.ingestor.multiqc_reader import read_multiqc


def write_multiqc(tmp_path, data: dict, filename: str = "multiqc_data.json"):
    p = tmp_path / filename
    p.write_text(json.dumps(data))
    return str(p)


FULL_MULTIQC = {
    "report_saved_raw_data": {
        "multiqc_kraken": {
            "sample1": {"U": {"unclassified": 200}, "S": {"Homo sapiens": 800}}
        },
        "multiqc_centrifuge_centrifuge": {
            "sample1": {"R": {"root": 900}, "S": {"Homo sapiens": 800}}
        },
        "diamond": {"sample1_diamond": {"queries_aligned": 723522}},
        "multiqc_fastqc": {"sample1": {"baz": 3}},
        "multiqc_fastp": {"sample1": {"qux": 4}},
        "multiqc_bowtie2": {"sample1": {"quux": 5}},
    }
}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_read_multiqc_returns_all_keys(tmp_path):
    from app.ingestor.models import MultiQCRaw

    path = write_multiqc(tmp_path, FULL_MULTIQC)
    result = read_multiqc(path)
    assert isinstance(result, MultiQCRaw)
    assert set(MultiQCRaw.model_fields.keys()) == {
        "kraken2",
        "centrifuge",
        "diamond",
        "fastqc",
        "fastp",
        "bowtie2",
    }


def test_read_multiqc_data_correct(tmp_path):
    path = write_multiqc(tmp_path, FULL_MULTIQC)
    result = read_multiqc(path)
    assert result.kraken2 == {
        "sample1": {"U": {"unclassified": 200}, "S": {"Homo sapiens": 800}}
    }
    assert result.fastp == {"sample1": {"qux": 4}}


# ---------------------------------------------------------------------------
# Missing / partial keys
# ---------------------------------------------------------------------------


def test_missing_report_saved_raw_data_returns_empty_dicts(tmp_path):
    path = write_multiqc(tmp_path, {"something_else": {}})
    result = read_multiqc(path)
    assert all(v == {} for v in result.model_dump().values())


def test_partial_keys_missing_returns_empty_dict(tmp_path):
    data = {"report_saved_raw_data": {"multiqc_kraken": {"s": {}}}}
    path = write_multiqc(tmp_path, data)
    result = read_multiqc(path)
    assert result.kraken2 == {"s": {}}
    assert result.centrifuge == {}
    assert result.fastp == {}


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_file_not_found_raises():
    with pytest.raises(FileNotFoundError):
        read_multiqc("/nonexistent/multiqc_data.json")
