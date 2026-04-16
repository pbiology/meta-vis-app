# tests/unit/test_taxpasta_reader.py

import textwrap
import pytest
from app.ingestor.taxpasta_reader import (
    load_taxpasta,
    extract_sample_profile,
    read_taxpasta,
    _superkingdom_from_lineage,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def write_tsv(tmp_path, content: str, filename: str = "taxpasta.tsv"):
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content))
    return str(p)


MINIMAL_TSV = """\
    taxonomy_id\tname\trank\tlineage\tSAMPLE1
    9606\tHomo sapiens\tspecies\tEukaryota;Chordata\t100
    1279\tStaphylococcus\tgenus\tBacteria;Firmicutes\t50
    0\tunclassified\t\t\t200
"""

ZERO_ABUNDANCE_TSV = """\
    taxonomy_id\tname\trank\tlineage\tSAMPLE1
    9606\tHomo sapiens\tspecies\tEukaryota;Chordata\t0
    1279\tStaphylococcus\tgenus\tBacteria;Firmicutes\t0
"""

NO_LINEAGE_TSV = """\
    taxonomy_id\tname\trank\tSAMPLE1
    9606\tHomo sapiens\tspecies\t100
    1279\tStaphylococcus\tgenus\t50
"""

MIXED_CASE_RANK_TSV = """\
    taxonomy_id\tname\trank\tlineage\tSAMPLE1
    10239\tViruses\tNo rank\tViruses\t500
    9606\tHomo sapiens\tSpecies\tEukaryota;Chordata\t100
"""


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_read_taxpasta_returns_records(tmp_path):
    path = write_tsv(tmp_path, MINIMAL_TSV)
    records = read_taxpasta(path, "SAMPLE1")
    assert len(records) == 3


def test_read_taxpasta_record_fields(tmp_path):
    path = write_tsv(tmp_path, MINIMAL_TSV)
    records = read_taxpasta(path, "SAMPLE1")
    record = next(r for r in records if r.taxon_id == 9606)
    assert record.name == "Homo sapiens"
    assert record.rank == "species"
    assert record.abundance == 100.0
    assert record.superkingdom == "Eukaryota"


def test_read_taxpasta_superkingdom_bacteria(tmp_path):
    path = write_tsv(tmp_path, MINIMAL_TSV)
    records = read_taxpasta(path, "SAMPLE1")
    record = next(r for r in records if r.taxon_id == 1279)
    assert record.superkingdom == "Bacteria"


# ---------------------------------------------------------------------------
# Zero-abundance filtering
# ---------------------------------------------------------------------------


def test_zero_abundance_rows_filtered(tmp_path):
    path = write_tsv(tmp_path, ZERO_ABUNDANCE_TSV)
    records = read_taxpasta(path, "SAMPLE1")
    assert records == []


# ---------------------------------------------------------------------------
# No lineage column
# ---------------------------------------------------------------------------


def test_no_lineage_column_superkingdom_is_none(tmp_path):
    path = write_tsv(tmp_path, NO_LINEAGE_TSV)
    records = read_taxpasta(path, "SAMPLE1")
    assert all(r.superkingdom is None for r in records)


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_file_not_found_raises():
    with pytest.raises(FileNotFoundError):
        read_taxpasta("/nonexistent/path/taxpasta.tsv", "SAMPLE1")


def test_missing_taxonomy_id_column_raises(tmp_path):
    path = write_tsv(tmp_path, "name\tSAMPLE1\nfoo\t10\n")
    with pytest.raises(ValueError, match="missing required columns"):
        read_taxpasta(path, "SAMPLE1")


def test_missing_sample_column_raises(tmp_path):
    path = write_tsv(tmp_path, MINIMAL_TSV)
    with pytest.raises(ValueError, match="not found in TAXPASTA file"):
        read_taxpasta(path, "NONEXISTENT_SAMPLE")


# ---------------------------------------------------------------------------
# Rank normalisation
# ---------------------------------------------------------------------------


def test_rank_normalised_to_lowercase(tmp_path):
    path = write_tsv(tmp_path, MIXED_CASE_RANK_TSV)
    records = read_taxpasta(path, "SAMPLE1")
    virus = next(r for r in records if r.taxon_id == 10239)
    human = next(r for r in records if r.taxon_id == 9606)
    assert virus.rank == "no rank"
    assert human.rank == "species"


# ---------------------------------------------------------------------------
# _superkingdom_from_lineage unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "lineage, expected",
    [
        ("Bacteria;Firmicutes;Bacilli", "Bacteria"),
        ("Eukaryota;Chordata;Mammalia", "Eukaryota"),
        ("Viruses;Coronaviridae", "Viruses"),
        ("Archaea;Euryarchaeota", "Archaea"),
        ("", None),
        (None, None),
        ("Unknown;Something", None),
    ],
)
def test_superkingdom_from_lineage(lineage, expected):
    assert _superkingdom_from_lineage(lineage) == expected


# ---------------------------------------------------------------------------
# load_taxpasta
# ---------------------------------------------------------------------------


def test_load_taxpasta_returns_dataframe(tmp_path):
    path = write_tsv(tmp_path, MINIMAL_TSV)
    df = load_taxpasta(path)
    assert "taxon_id" in df.columns
    assert "taxonomy_id" not in df.columns  # renamed


def test_load_taxpasta_taxon_id_is_int(tmp_path):
    path = write_tsv(tmp_path, MINIMAL_TSV)
    df = load_taxpasta(path)
    assert df["taxon_id"].dtype == int


def test_load_taxpasta_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_taxpasta("/nonexistent/taxpasta.tsv")


def test_load_taxpasta_missing_required_column(tmp_path):
    path = write_tsv(tmp_path, "name\tSAMPLE1\nfoo\t10\n")
    with pytest.raises(ValueError, match="missing required columns"):
        load_taxpasta(path)


def test_load_taxpasta_keeps_zero_abundance_rows(tmp_path):
    """load_taxpasta must NOT filter by abundance — that is extract_sample_profile's job."""
    path = write_tsv(tmp_path, ZERO_ABUNDANCE_TSV)
    df = load_taxpasta(path)
    assert len(df) == 2


# ---------------------------------------------------------------------------
# extract_sample_profile
# ---------------------------------------------------------------------------


def test_extract_sample_profile_returns_records(tmp_path):
    path = write_tsv(tmp_path, MINIMAL_TSV)
    df = load_taxpasta(path)
    records = extract_sample_profile(df, "SAMPLE1")
    assert len(records) == 3


def test_extract_sample_profile_filters_zero_abundance(tmp_path):
    path = write_tsv(tmp_path, ZERO_ABUNDANCE_TSV)
    df = load_taxpasta(path)
    records = extract_sample_profile(df, "SAMPLE1")
    assert records == []


def test_extract_sample_profile_missing_column_raises(tmp_path):
    path = write_tsv(tmp_path, MINIMAL_TSV)
    df = load_taxpasta(path)
    with pytest.raises(ValueError, match="not found in TAXPASTA file"):
        extract_sample_profile(df, "NONEXISTENT")


def test_extract_sample_profile_correct_fields(tmp_path):
    path = write_tsv(tmp_path, MINIMAL_TSV)
    df = load_taxpasta(path)
    records = extract_sample_profile(df, "SAMPLE1")
    record = next(r for r in records if r.taxon_id == 9606)
    assert record.name == "Homo sapiens"
    assert record.rank == "species"
    assert record.abundance == 100.0
    assert record.superkingdom == "Eukaryota"


def test_load_once_extract_twice_same_result(tmp_path):
    """Loading once and slicing twice must give same result as two read_taxpasta calls."""
    tsv = """\
        taxonomy_id\tname\trank\tlineage\tSAMPLE1\tSAMPLE2
        9606\tHomo sapiens\tspecies\tEukaryota;Chordata\t100\t200
        1279\tStaphylococcus\tgenus\tBacteria;Firmicutes\t50\t0
    """
    path = write_tsv(tmp_path, tsv)
    df = load_taxpasta(path)

    r1_cached = extract_sample_profile(df, "SAMPLE1")
    r2_cached = extract_sample_profile(df, "SAMPLE2")

    r1_direct = read_taxpasta(path, "SAMPLE1")
    r2_direct = read_taxpasta(path, "SAMPLE2")

    assert [(r.taxon_id, r.abundance) for r in r1_cached] == [
        (r.taxon_id, r.abundance) for r in r1_direct
    ]
    assert [(r.taxon_id, r.abundance) for r in r2_cached] == [
        (r.taxon_id, r.abundance) for r in r2_direct
    ]
