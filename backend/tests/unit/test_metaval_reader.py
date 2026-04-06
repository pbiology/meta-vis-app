# tests/unit/test_metaval_reader.py

import pytest
from app.ingestor.metaval_reader import (
    _parse_igv_filename,
    _read_viral_taxids,
    _read_blast,
    read_metaval,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_igv_dir(tmp_path):
    igv_dir = tmp_path / "igv"
    igv_dir.mkdir()
    return igv_dir


def make_viral_taxids_dir(tmp_path, classifier="kraken2", entries: list[tuple] = None):
    taxids_dir = tmp_path / "viral_taxids"
    taxids_dir.mkdir(exist_ok=True)
    tsv = taxids_dir / f"SAMPLE1_{classifier}_viral_taxids.tsv"
    lines = "\n".join(f"{tid}\t{name}" for tid, name in (entries or []))
    tsv.write_text(lines)
    return taxids_dir


def make_blast_dir(tmp_path, classifier="kraken2", filename=None, content=None):
    blast_dir = tmp_path / "blast" / "blastn" / classifier
    blast_dir.mkdir(parents=True, exist_ok=True)
    if filename and content is not None:
        f = blast_dir / filename
        f.write_text(content)
    return blast_dir


BLAST_SUMMARY_CONTENT = (
    "qseqid\tstaxid\tssciname\tcount\n"
    "NODE_1\t2886042\tShigella virus Moo19\t1\n"
    "NODE_2\t2886042\tShigella virus Moo19\t1\n"
)


# ---------------------------------------------------------------------------
# _parse_igv_filename
# ---------------------------------------------------------------------------

class TestParseIgvFilename:

    def test_kraken2_happy_path(self):
        result = _parse_igv_filename(
            "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html"
        )
        assert result == {
            "sample_name":   "SRR13439790",
            "classifier":    "kraken2",
            "taxon_name":    "Shigella-virus-Moo19",
            "organism_name": "Shigella-virus-Moo19",
        }

    def test_centrifuge_happy_path(self):
        result = _parse_igv_filename(
            "SRR13439790_centrifuge_Enquatrovirus-N4_mappingorganism_Shigella-virus-Moo19_report.html"
        )
        assert result["classifier"]    == "centrifuge"
        assert result["taxon_name"]    == "Enquatrovirus-N4"
        assert result["organism_name"] == "Shigella-virus-Moo19"

    def test_diamond_happy_path(self):
        result = _parse_igv_filename(
            "SRR13439790_diamond_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html"
        )
        assert result["classifier"] == "diamond"

    def test_different_taxon_and_organism(self):
        result = _parse_igv_filename(
            "SRR13439790_kraken2_Gamaleyavirus_mappingorganism_Escherichia-phage-IME11_report.html"
        )
        assert result["taxon_name"]    == "Gamaleyavirus"
        assert result["organism_name"] == "Escherichia-phage-IME11"

    def test_returns_none_for_no_match(self):
        assert _parse_igv_filename("not_a_valid_filename.html") is None

    def test_returns_none_for_missing_report_suffix(self):
        assert _parse_igv_filename(
            "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19.html"
        ) is None

    def test_returns_none_for_unknown_classifier(self):
        assert _parse_igv_filename(
            "SRR13439790_blast_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html"
        ) is None


# ---------------------------------------------------------------------------
# _read_viral_taxids
# ---------------------------------------------------------------------------

class TestReadViralTaxids:

    def test_happy_path(self, tmp_path):
        make_viral_taxids_dir(tmp_path, "kraken2", [
            (2886042, "Shigella-virus-Moo19"),
            (335341,  "Influenza-A-virus-A-New-York-392-2004-H3N2"),
        ])
        result = _read_viral_taxids(tmp_path)
        assert result[("kraken2", "Shigella-virus-Moo19")] == 2886042
        assert result[("kraken2", "Influenza-A-virus-A-New-York-392-2004-H3N2")] == 335341

    def test_missing_directory_returns_empty_dict(self, tmp_path):
        result = _read_viral_taxids(tmp_path)
        assert result == {}

    def test_multiple_classifiers(self, tmp_path):
        make_viral_taxids_dir(tmp_path, "kraken2",    [(1111, "Virus-A")])
        make_viral_taxids_dir(tmp_path, "centrifuge", [(2222, "Virus-B")])
        result = _read_viral_taxids(tmp_path)
        assert result[("kraken2",    "Virus-A")] == 1111
        assert result[("centrifuge", "Virus-B")] == 2222

    def test_malformed_line_non_integer_taxid_skipped(self, tmp_path):
        taxids_dir = tmp_path / "viral_taxids"
        taxids_dir.mkdir()
        tsv = taxids_dir / "SAMPLE1_kraken2_viral_taxids.tsv"
        tsv.write_text("not_an_int\tVirus-A\n2886042\tVirus-B\n")
        result = _read_viral_taxids(tmp_path)
        assert ("kraken2", "Virus-A") not in result
        assert result[("kraken2", "Virus-B")] == 2886042

    def test_line_with_too_few_columns_skipped(self, tmp_path):
        taxids_dir = tmp_path / "viral_taxids"
        taxids_dir.mkdir()
        tsv = taxids_dir / "SAMPLE1_kraken2_viral_taxids.tsv"
        tsv.write_text("2886042\n")  # only one column
        result = _read_viral_taxids(tmp_path)
        assert result == {}

    def test_empty_lines_skipped(self, tmp_path):
        taxids_dir = tmp_path / "viral_taxids"
        taxids_dir.mkdir()
        tsv = taxids_dir / "SAMPLE1_kraken2_viral_taxids.tsv"
        tsv.write_text("\n\n2886042\tShigella-virus-Moo19\n\n")
        result = _read_viral_taxids(tmp_path)
        assert result[("kraken2", "Shigella-virus-Moo19")] == 2886042


# ---------------------------------------------------------------------------
# _read_blast
# ---------------------------------------------------------------------------

class TestReadBlast:

    def test_happy_path_rows_parsed(self, tmp_path):
        make_blast_dir(
            tmp_path, "kraken2",
            "SRR13439790_Shigella-virus-Moo19_blast_filtered_summary.txt",
            BLAST_SUMMARY_CONTENT,
        )
        result = _read_blast(tmp_path)
        rows = result[("SRR13439790_Shigella-virus-Moo19", "kraken2")]
        assert len(rows) == 2
        assert rows[0]["qseqid"] == "NODE_1"
        assert rows[0]["ssciname"] == "Shigella virus Moo19"

    def test_column_headers_used_as_keys(self, tmp_path):
        make_blast_dir(
            tmp_path, "kraken2",
            "SRR13439790_Shigella-virus-Moo19_blast_filtered_summary.txt",
            BLAST_SUMMARY_CONTENT,
        )
        result = _read_blast(tmp_path)
        rows = result[("SRR13439790_Shigella-virus-Moo19", "kraken2")]
        assert set(rows[0].keys()) == {"qseqid", "staxid", "ssciname", "count"}

    def test_empty_file_skipped(self, tmp_path):
        make_blast_dir(
            tmp_path, "kraken2",
            "SRR13439790_Shigella-virus-Moo19_blast_filtered_summary.txt",
            "",
        )
        result = _read_blast(tmp_path)
        assert result == {}

    def test_header_only_file_skipped(self, tmp_path):
        make_blast_dir(
            tmp_path, "kraken2",
            "SRR13439790_Shigella-virus-Moo19_blast_filtered_summary.txt",
            "qseqid\tstaxid\tssciname\tcount\n",
        )
        result = _read_blast(tmp_path)
        assert result == {}

    def test_missing_blast_directory_returns_empty_dict(self, tmp_path):
        result = _read_blast(tmp_path)
        assert result == {}

    def test_multiple_classifiers_read(self, tmp_path):
        make_blast_dir(
            tmp_path, "kraken2",
            "SRR13439790_Virus-A_blast_filtered_summary.txt",
            BLAST_SUMMARY_CONTENT,
        )
        make_blast_dir(
            tmp_path, "centrifuge",
            "SRR13439790_Virus-B_blast_filtered_summary.txt",
            BLAST_SUMMARY_CONTENT,
        )
        result = _read_blast(tmp_path)
        assert ("SRR13439790_Virus-A", "kraken2")    in result
        assert ("SRR13439790_Virus-B", "centrifuge") in result


# ---------------------------------------------------------------------------
# read_metaval
# ---------------------------------------------------------------------------

class TestReadMetaval:

    def test_missing_igv_directory_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_metaval(str(tmp_path / "nonexistent" / "igv"))

    def test_empty_igv_directory_returns_empty_results(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        result = read_metaval(str(igv_dir))
        assert result["results"] == []

    def test_happy_path_groups_by_sample_classifier_taxon(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (igv_dir / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html").write_text("<html/>")
        (igv_dir / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Escherichia-phage-IME11_report.html").write_text("<html/>")
        result = read_metaval(str(igv_dir))
        assert len(result["results"]) == 1
        assert len(result["results"][0]["organisms"]) == 2

    def test_taxon_id_resolved_from_taxid_map(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (igv_dir / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html").write_text("<html/>")
        make_viral_taxids_dir(tmp_path, "kraken2", [(2886042, "Shigella-virus-Moo19")])
        result = read_metaval(str(igv_dir))
        assert result["results"][0]["taxon_id"] == 2886042

    def test_taxon_id_is_none_when_not_in_taxid_map(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (igv_dir / "SRR13439790_kraken2_Unknown-virus_mappingorganism_Unknown-virus_report.html").write_text("<html/>")
        result = read_metaval(str(igv_dir))
        assert result["results"][0]["taxon_id"] is None

    def test_igv_within_size_limit_is_read(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        html_file = igv_dir / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html"
        html_file.write_text("<html>content</html>")
        result = read_metaval(str(igv_dir))
        org = result["results"][0]["organisms"][0]
        assert org["igv_file_path"] == str(html_file)
        assert org["igv_too_large"] is False

    def test_igv_exceeding_size_limit_sets_too_large(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        large_file = igv_dir / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html"
        large_file.write_bytes(b"x" * (10 * 1024 * 1024 + 1))
        result = read_metaval(str(igv_dir))
        org = result["results"][0]["organisms"][0]
        assert org["igv_too_large"] is True
        assert org["igv_file_path"] == str(large_file)

    def test_blast_hits_matched_to_result(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (igv_dir / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html").write_text("<html/>")
        make_blast_dir(
            tmp_path, "kraken2",
            "SRR13439790_Shigella-virus-Moo19_blast_filtered_summary.txt",
            BLAST_SUMMARY_CONTENT,
        )
        result = read_metaval(str(igv_dir))
        assert len(result["results"][0]["blast"]) == 2

    def test_no_blast_data_gives_empty_blast_list(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (igv_dir / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html").write_text("<html/>")
        result = read_metaval(str(igv_dir))
        assert result["results"][0]["blast"] == []

    def test_unrecognised_igv_filenames_ignored(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (igv_dir / "not_a_valid_filename.html").write_text("<html/>")
        result = read_metaval(str(igv_dir))
        assert result["results"] == []

    def test_pipeline_info_key_present_in_result(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        result = read_metaval(str(igv_dir))
        assert "pipeline_info" in result