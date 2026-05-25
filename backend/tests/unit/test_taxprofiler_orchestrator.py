# tests/unit/test_orchestrator.py

from app.ingestor.inputs import MultiQCRaw
from app.ingestor.orchestrator import _extract_classifier_qc, _extract_base_qc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_multiqc(
    kraken2: dict | None = None,
    centrifuge: dict | None = None,
    diamond: dict | None = None,
    fastqc: dict | None = None,
    fastp: dict | None = None,
    bowtie2: dict | None = None,
) -> MultiQCRaw:
    return MultiQCRaw(
        kraken2=kraken2 or {},
        centrifuge=centrifuge or {},
        diamond=diamond or {},
        fastqc=fastqc or {},
        fastp=fastp or {},
        bowtie2=bowtie2 or {},
    )


def make_kraken2_records(
    unclassified=200,
    classified=800,
    num_species=10,
    num_genera=5,
):
    """MultiQC v2 dict-of-dicts format."""
    return {
        "U": {"unclassified": unclassified},
        "R": {"root": classified},
        "S": {f"Species-{i}": 10 for i in range(num_species)},
        "G": {f"Genus-{i}": 20 for i in range(num_genera)},
    }


def make_centrifuge_records(num_species=3, num_genera=2):
    """MultiQC v2 dict-of-dicts format. No R key — classified falls back to species sum."""
    return {
        "S": {f"Species-{i}": 100 for i in range(num_species)},
        "G": {f"Genus-{i}": 50 for i in range(num_genera)},
    }


def make_fastp_lane(
    total_before=1000000,
    total_after=950000,
    passed=940000,
    low_quality=50000,
    too_short=10000,
    q20=0.98,
    q30=0.92,
    gc=0.50,
):
    return {
        "summary": {
            "before_filtering": {"total_reads": total_before},
            "after_filtering": {
                "total_reads": total_after,
                "q20_rate": q20,
                "q30_rate": q30,
                "gc_content": gc,
            },
        },
        "filtering_result": {
            "passed_filter_reads": passed,
            "low_quality_reads": low_quality,
            "too_short_reads": too_short,
        },
    }


def make_bowtie2_lane(total=900000, one=100000, multi=50000, none=750000, rate=11.1):
    return {
        "total_reads": total,
        "paired_aligned_one": one,
        "paired_aligned_multi": multi,
        "paired_aligned_none": none,
        "overall_alignment_rate": rate,
    }


# ---------------------------------------------------------------------------
# _extract_classifier_qc — kraken2
# ---------------------------------------------------------------------------


class TestExtractClassifierQcKraken2:
    def _qc_data(self, col="SAMPLE1_k2_pluspf.kraken2.kraken2.report", records=None):
        key = col.split(".kraken2")[0]
        return make_multiqc(
            kraken2={key: make_kraken2_records() if records is None else records}
        )

    def test_happy_path_returns_expected_fields(self):
        result = _extract_classifier_qc(
            self._qc_data(), "kraken2", "SAMPLE1_k2_pluspf.kraken2.kraken2.report"
        )
        assert set(result.keys()) == {
            "pct_unclassified",
            "unclassified_reads",
            "classified_reads",
            "total_reads",
            "num_species",
            "num_genera",
        }

    def test_pct_unclassified_correct(self):
        records = make_kraken2_records(unclassified=200, classified=800)
        result = _extract_classifier_qc(
            self._qc_data(records=records),
            "kraken2",
            "SAMPLE1_k2_pluspf.kraken2.kraken2.report",
        )
        assert result["pct_unclassified"] == 20.0

    def test_classified_reads_from_root_record(self):
        records = make_kraken2_records(classified=800)
        result = _extract_classifier_qc(
            self._qc_data(records=records),
            "kraken2",
            "SAMPLE1_k2_pluspf.kraken2.kraken2.report",
        )
        assert result["classified_reads"] == 800

    def test_num_species_and_genera(self):
        records = make_kraken2_records(num_species=7, num_genera=3)
        result = _extract_classifier_qc(
            self._qc_data(records=records),
            "kraken2",
            "SAMPLE1_k2_pluspf.kraken2.kraken2.report",
        )
        assert result["num_species"] == 7
        assert result["num_genera"] == 3

    def test_column_suffix_stripped_correctly(self):
        col = "MYSAMPLE_k2_pluspf.kraken2.kraken2.report"
        key = "MYSAMPLE_k2_pluspf"
        qc_data = make_multiqc(kraken2={key: make_kraken2_records()})
        result = _extract_classifier_qc(qc_data, "kraken2", col)
        assert result != {}

    def test_zero_total_reads_pct_is_none(self):
        records = make_kraken2_records(unclassified=0, classified=0)
        result = _extract_classifier_qc(
            self._qc_data(records=records),
            "kraken2",
            "SAMPLE1_k2_pluspf.kraken2.kraken2.report",
        )
        assert result["pct_unclassified"] is None

    def test_all_zero_counts_become_none(self):
        records = make_kraken2_records(
            unclassified=0, classified=0, num_species=0, num_genera=0
        )
        result = _extract_classifier_qc(
            self._qc_data(records=records),
            "kraken2",
            "SAMPLE1_k2_pluspf.kraken2.kraken2.report",
        )
        assert result["unclassified_reads"] is None
        assert result["classified_reads"] is None
        assert result["num_species"] is None
        assert result["num_genera"] is None

    def test_missing_key_returns_empty_dict(self):
        result = _extract_classifier_qc(
            make_multiqc(kraken2={}),
            "kraken2",
            "SAMPLE1_k2_pluspf.kraken2.kraken2.report",
        )
        assert result == {}

    def test_empty_records_returns_empty_dict(self):
        result = _extract_classifier_qc(
            self._qc_data(records={}),
            "kraken2",
            "SAMPLE1_k2_pluspf.kraken2.kraken2.report",
        )
        assert result == {}


# ---------------------------------------------------------------------------
# _extract_classifier_qc — centrifuge
# ---------------------------------------------------------------------------


class TestExtractClassifierQcCentrifuge:
    def _qc_data(self, col="SAMPLE1_p_compressed+h+v.centrifuge", records=None):
        return make_multiqc(centrifuge={col: records or make_centrifuge_records()})

    def test_happy_path_returns_expected_fields(self):
        result = _extract_classifier_qc(
            self._qc_data(), "centrifuge", "SAMPLE1_p_compressed+h+v.centrifuge"
        )
        assert "num_species" in result
        assert "classified_reads" in result

    def test_no_root_record_falls_back_to_species_sum(self):
        # centrifuge has no R record — classified = sum of species counts_rooted
        records = make_centrifuge_records(num_species=3)
        result = _extract_classifier_qc(
            self._qc_data(records=records),
            "centrifuge",
            "SAMPLE1_p_compressed+h+v.centrifuge",
        )
        assert result["classified_reads"] == 300  # 3 species × 100

    def test_num_species_correct(self):
        records = make_centrifuge_records(num_species=5)
        result = _extract_classifier_qc(
            self._qc_data(records=records),
            "centrifuge",
            "SAMPLE1_p_compressed+h+v.centrifuge",
        )
        assert result["num_species"] == 5


# ---------------------------------------------------------------------------
# _extract_classifier_qc — diamond
# ---------------------------------------------------------------------------


class TestExtractClassifierQcDiamond:
    def _qc_data(self, col="SAMPLE1_diamond.diamond", queries_aligned=723522):
        key = col.split(".diamond")[0]
        return make_multiqc(diamond={key: {"queries_aligned": queries_aligned}})

    def test_happy_path_returns_queries_aligned(self):
        result = _extract_classifier_qc(
            self._qc_data(), "diamond", "SAMPLE1_diamond.diamond"
        )
        assert result == {"queries_aligned": 723522}

    def test_column_suffix_stripped_correctly(self):
        col = "26CE100005-DNA_diamond.diamond"
        key = "26CE100005-DNA_diamond"
        qc_data = make_multiqc(diamond={key: {"queries_aligned": 100}})
        result = _extract_classifier_qc(qc_data, "diamond", col)
        assert result["queries_aligned"] == 100

    def test_missing_key_returns_empty_dict(self):
        result = _extract_classifier_qc(
            make_multiqc(), "diamond", "SAMPLE1_diamond.diamond"
        )
        assert result == {}

    def test_zero_queries_aligned_becomes_none(self):
        result = _extract_classifier_qc(
            self._qc_data(queries_aligned=0), "diamond", "SAMPLE1_diamond.diamond"
        )
        assert result["queries_aligned"] is None


# ---------------------------------------------------------------------------
# _extract_classifier_qc — unknown classifier
# ---------------------------------------------------------------------------


def test_unknown_classifier_returns_empty_dict():
    result = _extract_classifier_qc(make_multiqc(), "blast", "SAMPLE1")
    assert result == {}


# ---------------------------------------------------------------------------
# _extract_base_qc — fastp
# ---------------------------------------------------------------------------


class TestExtractBaseQcFastp:
    def _qc_data(self, sample_id="SAMPLE1", lane_suffix="_1", **kwargs):
        return make_multiqc(
            fastp={f"{sample_id}{lane_suffix}": make_fastp_lane(**kwargs)}
        )

    def test_happy_path_fields_present(self):
        result = _extract_base_qc(self._qc_data(), "SAMPLE1")
        assert "fastp" in result
        assert set(result["fastp"].keys()) == {
            "total_reads_before_filtering",
            "total_reads_after_filtering",
            "passed_filter_reads",
            "low_quality_reads",
            "too_short_reads",
            "q20_rate",
            "q30_rate",
            "gc_content",
        }

    def test_total_reads_correct(self):
        result = _extract_base_qc(self._qc_data(total_before=1000000), "SAMPLE1")
        assert result["fastp"]["total_reads_before_filtering"] == 1000000

    def test_q30_rate_correct(self):
        result = _extract_base_qc(self._qc_data(q30=0.92), "SAMPLE1")
        assert result["fastp"]["q30_rate"] == 0.92

    def test_multi_lane_reads_summed(self):
        qc_data = make_multiqc(
            fastp={
                "SAMPLE1_1": make_fastp_lane(total_before=500000),
                "SAMPLE1_2": make_fastp_lane(total_before=500000),
            }
        )
        result = _extract_base_qc(qc_data, "SAMPLE1")
        assert result["fastp"]["total_reads_before_filtering"] == 1000000

    def test_multi_lane_rates_averaged(self):
        qc_data = make_multiqc(
            fastp={
                "SAMPLE1_1": make_fastp_lane(q30=0.90),
                "SAMPLE1_2": make_fastp_lane(q30=0.80),
            }
        )
        result = _extract_base_qc(qc_data, "SAMPLE1")
        assert result["fastp"]["q30_rate"] == 0.85

    def test_sample_not_present_no_fastp_key(self):
        result = _extract_base_qc(make_multiqc(), "SAMPLE1")
        assert "fastp" not in result


# ---------------------------------------------------------------------------
# _extract_base_qc — bowtie2
# ---------------------------------------------------------------------------


class TestExtractBaseQcBowtie2:
    def _qc_data(self, sample_id="SAMPLE1", lane_suffix="_1", **kwargs):
        return make_multiqc(
            bowtie2={f"{sample_id}{lane_suffix}": make_bowtie2_lane(**kwargs)}
        )

    def test_happy_path_fields_present(self):
        result = _extract_base_qc(self._qc_data(), "SAMPLE1")
        assert "bowtie2" in result
        assert "overall_alignment_rate" in result["bowtie2"]

    def test_alignment_rate_correct(self):
        result = _extract_base_qc(self._qc_data(rate=15.5), "SAMPLE1")
        assert result["bowtie2"]["overall_alignment_rate"] == 15.5

    def test_total_reads_correct(self):
        result = _extract_base_qc(self._qc_data(total=900000), "SAMPLE1")
        assert result["bowtie2"]["total_reads"] == 900000

    def test_sample_not_present_no_bowtie2_key(self):
        result = _extract_base_qc(make_multiqc(), "SAMPLE1")
        assert "bowtie2" not in result


# ---------------------------------------------------------------------------
# _extract_base_qc — fastqc
# ---------------------------------------------------------------------------


class TestExtractBaseQcFastqc:
    def _qc_data(self, sample_id="SAMPLE1"):
        return make_multiqc(
            fastqc={
                f"{sample_id}_1_raw_1": {
                    "total_sequences": 500000,
                    "avg_sequence_length": 150.0,
                    "percent_gc": 48.0,
                    "percent_fails": 2.0,
                },
                f"{sample_id}_1_raw_2": {
                    "total_sequences": 500000,
                    "avg_sequence_length": 150.0,
                    "percent_gc": 50.0,
                    "percent_fails": 3.0,
                },
            }
        )

    def test_happy_path_fields_present(self):
        result = _extract_base_qc(self._qc_data(), "SAMPLE1")
        assert "fastqc" in result
        assert "pct_gc_forward" in result["fastqc"]
        assert "pct_gc_reverse" in result["fastqc"]

    def test_gc_forward_correct(self):
        result = _extract_base_qc(self._qc_data(), "SAMPLE1")
        assert result["fastqc"]["pct_gc_forward"] == 48.0

    def test_gc_reverse_correct(self):
        result = _extract_base_qc(self._qc_data(), "SAMPLE1")
        assert result["fastqc"]["pct_gc_reverse"] == 50.0

    def test_sample_not_present_no_fastqc_key(self):
        result = _extract_base_qc(make_multiqc(), "SAMPLE1")
        assert "fastqc" not in result


# ---------------------------------------------------------------------------
# _extract_base_qc — partial data
# ---------------------------------------------------------------------------


def test_fastp_present_bowtie2_absent():
    qc_data = make_multiqc(fastp={"SAMPLE1_1": make_fastp_lane()})
    result = _extract_base_qc(qc_data, "SAMPLE1")
    assert "fastp" in result
    assert "bowtie2" not in result


def test_bowtie2_present_fastp_absent():
    qc_data = make_multiqc(bowtie2={"SAMPLE1_1": make_bowtie2_lane()})
    result = _extract_base_qc(qc_data, "SAMPLE1")
    assert "bowtie2" in result
    assert "fastp" not in result


def test_empty_qc_data_returns_empty_dict():
    result = _extract_base_qc(make_multiqc(), "SAMPLE1")
    assert result == {}
