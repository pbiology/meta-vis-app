import json
from pathlib import Path


def _derive_multiqc_key(taxpasta_column: str) -> str:
    return taxpasta_column.split(".")[0]


def read_multiqc(file_path: str, taxpasta_column: str) -> dict:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"MultiQC file not found: {file_path}")

    with open(path) as f:
        data = json.load(f)

    sample_key = _derive_multiqc_key(taxpasta_column)
    sample_key_base = sample_key.split("_k2")[0]
    stats = {}

    # Kraken2 summary from general stats
    general_stats = (
        data
        .get("report_saved_raw_data", {})
        .get("multiqc_general_stats", {})
    )
    sample_general = general_stats.get(sample_key, {})
    if sample_general:
        stats["kraken2"] = {
            "pct_unclassified": sample_general.get("kraken-pct_unclassified"),
            "pct_top_one": sample_general.get("kraken-pct_top_one"),
            "pct_top_n": sample_general.get("kraken-pct_top_n"),
        }

    # Kraken2 per-rank read counts
    kraken2_data = (
        data
        .get("report_saved_raw_data", {})
        .get("multiqc_kraken", {})
    )
    sample_kraken = kraken2_data.get(sample_key, {})
    if sample_kraken:
        stats["kraken2"] = {
            **stats.get("kraken2", {}),
            "unclassified_reads": sample_kraken.get("U", {}).get("unclassified"),
            "num_species": len(sample_kraken.get("S", {})),
            "num_genera": len(sample_kraken.get("G", {})),
        }

    # FastQC — keys are {sample_base}_{read_pair}_raw_{direction}
    fastqc_data = (
        data
        .get("report_saved_raw_data", {})
        .get("multiqc_fastqc", {})
    )
    fastqc_fwd_keys = sorted([
        k for k in fastqc_data.keys()
        if k.startswith(sample_key_base) and k.endswith("_raw_1")
    ])
    fastqc_rev_keys = sorted([
        k for k in fastqc_data.keys()
        if k.startswith(sample_key_base) and k.endswith("_raw_2")
    ])
    if fastqc_fwd_keys:
        first_fwd = fastqc_data[fastqc_fwd_keys[0]]
        first_rev = fastqc_data[fastqc_rev_keys[0]] if fastqc_rev_keys else {}
        total_sequences = sum(
            fastqc_data[k].get("Total Sequences", 0)
            for k in fastqc_fwd_keys
        )
        stats["fastqc"] = {
            "total_sequences": total_sequences,
            "avg_sequence_length": first_fwd.get("avg_sequence_length"),
            "pct_gc_forward": first_fwd.get("%GC"),
            "pct_gc_reverse": first_rev.get("%GC"),
            "pct_poor_quality_forward": first_fwd.get("Sequences flagged as poor quality"),
            "pct_poor_quality_reverse": first_rev.get("Sequences flagged as poor quality"),
        }

    # Bowtie2 — keys are {sample_base}_{read_pair}
    bowtie2_data = (
        data
        .get("report_saved_raw_data", {})
        .get("multiqc_bowtie2", {})
    )
    bowtie2_keys = [
        k for k in bowtie2_data.keys()
        if k.startswith(sample_key_base)
    ]
    if bowtie2_keys:
        total_reads = sum(
            bowtie2_data[k].get("total_reads", 0)
            for k in bowtie2_keys
        )
        total_aligned_one = sum(
            bowtie2_data[k].get("paired_aligned_one", 0)
            for k in bowtie2_keys
        )
        total_aligned_multi = sum(
            bowtie2_data[k].get("paired_aligned_multi", 0)
            for k in bowtie2_keys
        )
        total_aligned_none = sum(
            bowtie2_data[k].get("paired_aligned_none", 0)
            for k in bowtie2_keys
        )
        stats["bowtie2"] = {
            "total_reads": total_reads,
            "aligned_exactly_one": total_aligned_one,
            "aligned_multi": total_aligned_multi,
            "aligned_none": total_aligned_none,
            "overall_alignment_rate": bowtie2_data[bowtie2_keys[0]].get("overall_alignment_rate"),
        }

    # Fastp — keys are {sample_base}_{read_pair}
    fastp_data = (
        data
        .get("report_saved_raw_data", {})
        .get("multiqc_fastp", {})
    )
    fastp_keys = [
        k for k in fastp_data.keys()
        if k.startswith(sample_key_base)
    ]
    if fastp_keys:
        total_reads_before = sum(
            fastp_data[k].get("summary", {}).get("before_filtering", {}).get("total_reads", 0)
            for k in fastp_keys
        )
        total_reads_after = sum(
            fastp_data[k].get("summary", {}).get("after_filtering", {}).get("total_reads", 0)
            for k in fastp_keys
        )
        total_passed_filter = sum(
            fastp_data[k].get("filtering_result", {}).get("passed_filter_reads", 0)
            for k in fastp_keys
        )
        total_low_quality = sum(
            fastp_data[k].get("filtering_result", {}).get("low_quality_reads", 0)
            for k in fastp_keys
        )
        total_too_short = sum(
            fastp_data[k].get("filtering_result", {}).get("too_short_reads", 0)
            for k in fastp_keys
        )
        first = fastp_data[fastp_keys[0]]
        stats["fastp"] = {
            "total_reads_before_filtering": total_reads_before,
            "total_reads_after_filtering": total_reads_after,
            "passed_filter_reads": total_passed_filter,
            "low_quality_reads": total_low_quality,
            "too_short_reads": total_too_short,
            "q20_rate": first.get("summary", {}).get("before_filtering", {}).get("q20_rate"),
            "q30_rate": first.get("summary", {}).get("before_filtering", {}).get("q30_rate"),
            "gc_content": first.get("summary", {}).get("before_filtering", {}).get("gc_content"),
        }

    return stats