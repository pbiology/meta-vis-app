# tests/unit/test_metaval_reader.py

import pytest
from typing import Optional
from app.ingestor.metaval_reader import (
    _parse_igv_filename,
    _read_viral_taxids,
    _read_blast,
    _read_extracted_reads,
    _read_spades,
    _read_metaval_pipeline_info,
    _fasta_stats,
    read_metaval,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_igv_dir(tmp_path):
    igv_dir = tmp_path / "igv"
    igv_dir.mkdir()
    return igv_dir


def make_viral_taxids_dir(
    tmp_path, classifier="kraken2", entries: Optional[list[tuple]] = None
):
    taxids_dir = tmp_path / "viral_taxids"
    taxids_dir.mkdir(exist_ok=True)
    tsv = taxids_dir / f"SAMPLE1_{classifier}_viral_taxids.tsv"
    lines = "\n".join(f"{tid}\t{name}" for tid, name in (entries or []))
    tsv.write_text(lines)
    return taxids_dir


def make_blast_dir(
    tmp_path, classifier="kraken2", filename=None, content=None, program="blastn"
):
    blast_dir = tmp_path / "blast" / program / classifier
    blast_dir.mkdir(parents=True, exist_ok=True)
    if filename and content is not None:
        f = blast_dir / filename
        f.write_text(content)
    return blast_dir


FASTA_CONTENT = ">READ_1 length=10\nATCGATCGAT\n>READ_2 length=10\nGCTAGCTAGC\n"

SPADES_CONTENT = (
    ">NODE_1_length_20_cov_1.0\n"
    "ATCGATCGATGCTAGCTAGC\n"
    ">NODE_2_length_15_cov_1.5\n"
    "ATCGATCGATGCTAG\n"
)


def make_extracted_reads_dir(
    tmp_path, classifier="kraken2", name_part="SAMPLE1_Virus-A", content=None
):
    reads_dir = tmp_path / "extracted_reads" / classifier
    reads_dir.mkdir(parents=True, exist_ok=True)
    fa = reads_dir / f"{name_part}.extracted_{classifier}_read_1.fa"
    fa.write_text(content or FASTA_CONTENT)
    fa2 = reads_dir / f"{name_part}.extracted_{classifier}_read_2.fa"
    fa2.write_text(content or FASTA_CONTENT)
    return reads_dir


def make_spades_dir(
    tmp_path,
    classifier="kraken2",
    name_part="SAMPLE1_Virus-A",
    kind="scaffolds",
    content=None,
):
    spades_dir = tmp_path / "spades" / classifier
    spades_dir.mkdir(parents=True, exist_ok=True)
    fa = spades_dir / f"{name_part}.{kind}.fa"
    fa.write_text(content or SPADES_CONTENT)
    return spades_dir


BLAST_SUMMARY_CONTENT = (
    "qseqid\tstaxid\tssciname\tcount\n"
    "NODE_1\t2886042\tShigella virus Moo19\t1\n"
    "NODE_2\t2886042\tShigella virus Moo19\t1\n"
)

BLASTX_SUMMARY_CONTENT = (
    "qseqid\tstaxid\tssciname\tcount\tmin_pident\tmax_pident\tmedian_pident\tmin_length\tmax_length\tmedian_length\tmin_bitscore\tmax_bitscore\tmedian_bitscore\n"
    "NODE_1\t2886042\tShigella virus Moo19\t1\t94.8\t94.8\t94.8\t96\t96\t96.0\t190.0\t190.0\t190.0\n"
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
            "sample_name": "SRR13439790",
            "classifier": "kraken2",
            "taxon_name": "Shigella-virus-Moo19",
            "organism_name": "Shigella-virus-Moo19",
        }

    def test_centrifuge_happy_path(self):
        result = _parse_igv_filename(
            "SRR13439790_centrifuge_Enquatrovirus-N4_mappingorganism_Shigella-virus-Moo19_report.html"
        )
        assert result["classifier"] == "centrifuge"
        assert result["taxon_name"] == "Enquatrovirus-N4"
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
        assert result["taxon_name"] == "Gamaleyavirus"
        assert result["organism_name"] == "Escherichia-phage-IME11"

    def test_returns_none_for_no_match(self):
        assert _parse_igv_filename("not_a_valid_filename.html") is None

    def test_returns_none_for_missing_report_suffix(self):
        assert (
            _parse_igv_filename(
                "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19.html"
            )
            is None
        )

    def test_returns_none_for_unknown_classifier(self):
        assert (
            _parse_igv_filename(
                "SRR13439790_blast_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html"
            )
            is None
        )


# ---------------------------------------------------------------------------
# _read_viral_taxids
# ---------------------------------------------------------------------------


class TestReadViralTaxids:
    def test_happy_path(self, tmp_path):
        make_viral_taxids_dir(
            tmp_path,
            "kraken2",
            [
                (2886042, "Shigella-virus-Moo19"),
                (335341, "Influenza-A-virus-A-New-York-392-2004-H3N2"),
            ],
        )
        result = _read_viral_taxids(tmp_path)
        assert result[("kraken2", "Shigella-virus-Moo19")] == 2886042
        assert (
            result[("kraken2", "Influenza-A-virus-A-New-York-392-2004-H3N2")] == 335341
        )

    def test_missing_directory_returns_empty_dict(self, tmp_path):
        result = _read_viral_taxids(tmp_path)
        assert result == {}

    def test_multiple_classifiers(self, tmp_path):
        make_viral_taxids_dir(tmp_path, "kraken2", [(1111, "Virus-A")])
        make_viral_taxids_dir(tmp_path, "centrifuge", [(2222, "Virus-B")])
        result = _read_viral_taxids(tmp_path)
        assert result[("kraken2", "Virus-A")] == 1111
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
    def test_blastn_rows_parsed(self, tmp_path):
        make_blast_dir(
            tmp_path,
            "kraken2",
            "SRR13439790_Shigella-virus-Moo19_blast_filtered_summary.txt",
            BLAST_SUMMARY_CONTENT,
            program="blastn",
        )
        result = _read_blast(tmp_path)
        rows = result[("SRR13439790_Shigella-virus-Moo19", "kraken2")]["blastn"]
        assert len(rows) == 2
        assert rows[0]["qseqid"] == "NODE_1"
        assert rows[0]["ssciname"] == "Shigella virus Moo19"

    def test_blastx_rows_parsed(self, tmp_path):
        make_blast_dir(
            tmp_path,
            "kraken2",
            "SRR13439790_Shigella-virus-Moo19_blastx_filtered_summary.txt",
            BLASTX_SUMMARY_CONTENT,
            program="blastx",
        )
        result = _read_blast(tmp_path)
        rows = result[("SRR13439790_Shigella-virus-Moo19", "kraken2")]["blastx"]
        assert len(rows) == 1
        assert rows[0]["ssciname"] == "Shigella virus Moo19"

    def test_both_programs_combined_under_same_key(self, tmp_path):
        make_blast_dir(
            tmp_path,
            "kraken2",
            "SRR13439790_Shigella-virus-Moo19_blast_filtered_summary.txt",
            BLAST_SUMMARY_CONTENT,
            program="blastn",
        )
        make_blast_dir(
            tmp_path,
            "kraken2",
            "SRR13439790_Shigella-virus-Moo19_blastx_filtered_summary.txt",
            BLASTX_SUMMARY_CONTENT,
            program="blastx",
        )
        result = _read_blast(tmp_path)
        key = ("SRR13439790_Shigella-virus-Moo19", "kraken2")
        assert len(result[key]["blastn"]) == 2
        assert len(result[key]["blastx"]) == 1

    def test_empty_file_skipped(self, tmp_path):
        make_blast_dir(
            tmp_path,
            "kraken2",
            "SRR13439790_Shigella-virus-Moo19_blast_filtered_summary.txt",
            "",
            program="blastn",
        )
        result = _read_blast(tmp_path)
        assert result == {}

    def test_header_only_file_skipped(self, tmp_path):
        make_blast_dir(
            tmp_path,
            "kraken2",
            "SRR13439790_Shigella-virus-Moo19_blast_filtered_summary.txt",
            "qseqid\tstaxid\tssciname\tcount\n",
            program="blastn",
        )
        result = _read_blast(tmp_path)
        assert result == {}

    def test_missing_blast_directory_returns_empty_dict(self, tmp_path):
        result = _read_blast(tmp_path)
        assert result == {}

    def test_multiple_classifiers_read(self, tmp_path):
        make_blast_dir(
            tmp_path,
            "kraken2",
            "SRR13439790_Virus-A_blast_filtered_summary.txt",
            BLAST_SUMMARY_CONTENT,
            program="blastn",
        )
        make_blast_dir(
            tmp_path,
            "centrifuge",
            "SRR13439790_Virus-B_blast_filtered_summary.txt",
            BLAST_SUMMARY_CONTENT,
            program="blastn",
        )
        result = _read_blast(tmp_path)
        assert ("SRR13439790_Virus-A", "kraken2") in result
        assert ("SRR13439790_Virus-B", "centrifuge") in result


# ---------------------------------------------------------------------------
# _fasta_stats
# ---------------------------------------------------------------------------


class TestFastaStats:
    def test_counts_sequences(self, tmp_path):
        f = tmp_path / "test.fa"
        f.write_text(FASTA_CONTENT)
        stats = _fasta_stats(f)
        assert stats["count"] == 2

    def test_avg_length_correct(self, tmp_path):
        f = tmp_path / "test.fa"
        f.write_text(FASTA_CONTENT)
        stats = _fasta_stats(f)
        assert stats["avg_length"] == 10.0

    def test_empty_file_returns_zeros(self, tmp_path):
        f = tmp_path / "empty.fa"
        f.write_text("")
        stats = _fasta_stats(f)
        assert stats["count"] == 0
        assert stats["avg_length"] == 0


# ---------------------------------------------------------------------------
# _read_extracted_reads
# ---------------------------------------------------------------------------


class TestReadExtractedReads:
    def test_happy_path(self, tmp_path):
        make_extracted_reads_dir(tmp_path, "kraken2", "SAMPLE1_Virus-A")
        result = _read_extracted_reads(tmp_path)
        assert ("SAMPLE1_Virus-A", "kraken2") in result

    def test_stats_computed(self, tmp_path):
        make_extracted_reads_dir(tmp_path, "kraken2", "SAMPLE1_Virus-A")
        result = _read_extracted_reads(tmp_path)
        entry = result[("SAMPLE1_Virus-A", "kraken2")]
        assert entry["count"] == 2
        assert entry["avg_length"] == 10.0

    def test_read_2_path_populated(self, tmp_path):
        make_extracted_reads_dir(tmp_path, "kraken2", "SAMPLE1_Virus-A")
        result = _read_extracted_reads(tmp_path)
        entry = result[("SAMPLE1_Virus-A", "kraken2")]
        assert entry["read_2_path"] is not None
        assert entry["file_count"] == 2

    def test_single_end_file_count_is_1(self, tmp_path):
        reads_dir = tmp_path / "extracted_reads" / "kraken2"
        reads_dir.mkdir(parents=True, exist_ok=True)
        fa = reads_dir / "SAMPLE1_Virus-A.extracted_kraken2_read_1.fa"
        fa.write_text(FASTA_CONTENT)
        # No read_2 file created
        result = _read_extracted_reads(tmp_path)
        assert result[("SAMPLE1_Virus-A", "kraken2")]["file_count"] == 1

    def test_missing_directory_returns_empty(self, tmp_path):
        result = _read_extracted_reads(tmp_path)
        assert result == {}


# ---------------------------------------------------------------------------
# _read_spades
# ---------------------------------------------------------------------------


class TestReadSpades:
    def test_scaffolds_preferred_over_contigs(self, tmp_path):
        make_spades_dir(tmp_path, "kraken2", "SAMPLE1_Virus-A", "scaffolds")
        make_spades_dir(tmp_path, "kraken2", "SAMPLE1_Virus-A", "contigs")
        result = _read_spades(tmp_path)
        assert result[("SAMPLE1_Virus-A", "kraken2")]["type"] == "scaffolds"

    def test_falls_back_to_contigs(self, tmp_path):
        make_spades_dir(tmp_path, "kraken2", "SAMPLE1_Virus-A", "contigs")
        result = _read_spades(tmp_path)
        assert result[("SAMPLE1_Virus-A", "kraken2")]["type"] == "contigs"

    def test_stats_computed(self, tmp_path):
        make_spades_dir(tmp_path, "kraken2", "SAMPLE1_Virus-A", "scaffolds")
        result = _read_spades(tmp_path)
        entry = result[("SAMPLE1_Virus-A", "kraken2")]
        assert entry["count"] == 2
        assert entry["avg_length"] == 17.5

    def test_missing_directory_returns_empty(self, tmp_path):
        result = _read_spades(tmp_path)
        assert result == {}


# ---------------------------------------------------------------------------
# read_metaval — verification_data
# ---------------------------------------------------------------------------


class TestReadMetavalVerificationData:
    def test_spades_takes_priority_over_raw_reads(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (
            igv_dir / "SAMPLE1_kraken2_Virus-A_mappingorganism_Virus-A_report.html"
        ).write_text("<html/>")
        make_extracted_reads_dir(tmp_path, "kraken2", "SAMPLE1_Virus-A")
        make_spades_dir(tmp_path, "kraken2", "SAMPLE1_Virus-A", "scaffolds")
        result = read_metaval(str(tmp_path))
        assert result["results"][0]["verification_data"]["type"] == "scaffolds"

    def test_falls_back_to_raw_reads_when_no_spades(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (
            igv_dir / "SAMPLE1_kraken2_Virus-A_mappingorganism_Virus-A_report.html"
        ).write_text("<html/>")
        make_extracted_reads_dir(tmp_path, "kraken2", "SAMPLE1_Virus-A")
        result = read_metaval(str(tmp_path))
        assert result["results"][0]["verification_data"]["type"] == "raw_reads"

    def test_verification_data_has_stats(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (
            igv_dir / "SAMPLE1_kraken2_Virus-A_mappingorganism_Virus-A_report.html"
        ).write_text("<html/>")
        make_extracted_reads_dir(tmp_path, "kraken2", "SAMPLE1_Virus-A")
        result = read_metaval(str(tmp_path))
        vd = result["results"][0]["verification_data"]
        assert vd["count"] == 2
        assert vd["avg_length"] == 10.0

    def test_no_verification_data_gives_empty_dict(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (
            igv_dir / "SAMPLE1_kraken2_Virus-A_mappingorganism_Virus-A_report.html"
        ).write_text("<html/>")
        result = read_metaval(str(tmp_path))
        vd = result["results"][0]["verification_data"]
        assert vd["type"] == "raw_reads"
        assert vd["count"] == 0


# ---------------------------------------------------------------------------
# read_metaval
# ---------------------------------------------------------------------------


class TestReadMetaval:
    def test_missing_directory_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_metaval(str(tmp_path / "nonexistent"))

    def test_empty_igv_directory_returns_empty_results(self, tmp_path):
        make_igv_dir(tmp_path)
        result = read_metaval(str(tmp_path))
        assert result["results"] == []

    def test_happy_path_groups_by_sample_classifier_taxon(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (
            igv_dir
            / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html"
        ).write_text("<html/>")
        (
            igv_dir
            / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Escherichia-phage-IME11_report.html"
        ).write_text("<html/>")
        result = read_metaval(str(tmp_path))
        assert len(result["results"]) == 1
        assert len(result["results"][0]["organisms"]) == 2

    def test_taxon_id_resolved_from_taxid_map(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (
            igv_dir
            / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html"
        ).write_text("<html/>")
        make_viral_taxids_dir(tmp_path, "kraken2", [(2886042, "Shigella-virus-Moo19")])
        result = read_metaval(str(tmp_path))
        assert result["results"][0]["taxon_id"] == 2886042

    def test_taxon_id_is_none_when_not_in_taxid_map(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (
            igv_dir
            / "SRR13439790_kraken2_Unknown-virus_mappingorganism_Unknown-virus_report.html"
        ).write_text("<html/>")
        result = read_metaval(str(tmp_path))
        assert result["results"][0]["taxon_id"] is None

    def test_igv_within_size_limit_is_read(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        html_file = (
            igv_dir
            / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html"
        )
        html_file.write_text("<html>content</html>")
        result = read_metaval(str(tmp_path))
        org = result["results"][0]["organisms"][0]
        assert org["igv_file_path"] == str(html_file)
        assert org["igv_too_large"] is False

    def test_igv_exceeding_size_limit_sets_too_large(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        large_file = (
            igv_dir
            / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html"
        )
        large_file.write_bytes(b"x" * (10 * 1024 * 1024 + 1))
        result = read_metaval(str(tmp_path))
        org = result["results"][0]["organisms"][0]
        assert org["igv_too_large"] is True
        assert org["igv_file_path"] == str(large_file)

    def test_blastn_hits_matched_to_result(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (
            igv_dir
            / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html"
        ).write_text("<html/>")
        make_blast_dir(
            tmp_path,
            "kraken2",
            "SRR13439790_Shigella-virus-Moo19_blast_filtered_summary.txt",
            BLAST_SUMMARY_CONTENT,
            program="blastn",
        )
        result = read_metaval(str(tmp_path))
        assert len(result["results"][0]["blast"]["blastn"]) == 2

    def test_blastx_hits_matched_to_result(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (
            igv_dir
            / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html"
        ).write_text("<html/>")
        make_blast_dir(
            tmp_path,
            "kraken2",
            "SRR13439790_Shigella-virus-Moo19_blastx_filtered_summary.txt",
            BLASTX_SUMMARY_CONTENT,
            program="blastx",
        )
        result = read_metaval(str(tmp_path))
        assert len(result["results"][0]["blast"]["blastx"]) == 1

    def test_no_blast_data_gives_empty_dicts(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (
            igv_dir
            / "SRR13439790_kraken2_Shigella-virus-Moo19_mappingorganism_Shigella-virus-Moo19_report.html"
        ).write_text("<html/>")
        result = read_metaval(str(tmp_path))
        assert result["results"][0]["blast"] == {"blastn": [], "blastx": []}

    def test_unrecognised_igv_filenames_ignored(self, tmp_path):
        igv_dir = make_igv_dir(tmp_path)
        (igv_dir / "not_a_valid_filename.html").write_text("<html/>")
        result = read_metaval(str(tmp_path))
        assert result["results"] == []

    def test_pipeline_info_key_present_in_result(self, tmp_path):
        make_igv_dir(tmp_path)
        result = read_metaval(str(tmp_path))
        assert "pipeline_info" in result


# ---------------------------------------------------------------------------
# _read_metaval_pipeline_info
# ---------------------------------------------------------------------------


class TestReadMetavalPipelineInfo:
    def test_returns_none_when_pipeline_info_dir_missing(self, tmp_path):
        result = _read_metaval_pipeline_info(tmp_path)
        assert result is None

    def test_returns_none_when_no_yml_file(self, tmp_path):
        (tmp_path / "pipeline_info").mkdir()
        result = _read_metaval_pipeline_info(tmp_path)
        assert result is None

    def test_returns_pipeline_info_when_yml_present(self, tmp_path):
        pipeline_info_dir = tmp_path / "pipeline_info"
        pipeline_info_dir.mkdir()
        yml = pipeline_info_dir / "versions.yml"
        yml.write_text(
            "Workflow:\n  genomic-medicine-sweden/metaval: 1.0.0\n  Nextflow: 23.10.1\n"
        )
        result = _read_metaval_pipeline_info(tmp_path)
        assert result is not None
        assert (
            result["pipeline_configuration"]["pipeline_name"]
            == "genomic-medicine-sweden/metaval"
        )
        assert result["pipeline_configuration"]["nextflow"] == "23.10.1"

    def test_returns_none_when_yml_is_invalid(self, tmp_path):
        pipeline_info_dir = tmp_path / "pipeline_info"
        pipeline_info_dir.mkdir()
        yml = pipeline_info_dir / "versions.yml"
        yml.write_text("not: a: valid: pipeline: info\n")
        # Missing 'Workflow' key — read_pipeline_info raises ValueError, caught silently
        result = _read_metaval_pipeline_info(tmp_path)
        assert result is None
