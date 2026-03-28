import json
from pathlib import Path


def read_multiqc(file_path: str, sample_name: str) -> dict:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"MultiQC file not found: {file_path}")

    with open(path) as f:
        data = json.load(f)

    stats = {}

    kraken2_data = (
        data
        .get("report_saved_raw_data", {})
        .get("multiqc_kraken", {})
    )
    sample_kraken = kraken2_data.get(sample_name, {})
    if sample_kraken:
        stats["kraken2"] = {
            "num_otus": sample_kraken.get("n_unique_taxa"),
        }

    fastqc_data = (
        data
        .get("report_saved_raw_data", {})
        .get("multiqc_fastqc", {})
    )
    sample_fastqc_fwd = fastqc_data.get(f"{sample_name}_1", {})
    sample_fastqc_rev = fastqc_data.get(f"{sample_name}_2", {})
    if sample_fastqc_fwd or sample_fastqc_rev:
        stats["fastqc"] = {
            "mean_phred_score_forward": sample_fastqc_fwd.get("avg_sequence_quality"),
            "mean_phred_score_reverse": sample_fastqc_rev.get("avg_sequence_quality"),
            "total_num_reads": sample_fastqc_fwd.get("total_sequences"),
        }

    fastp_data = (
        data
        .get("report_saved_raw_data", {})
        .get("multiqc_fastp", {})
    )
    sample_fastp = fastp_data.get(sample_name, {})
    if sample_fastp:
        stats["fastp"] = {
            "num_trimmed_reads": sample_fastp.get("filtering_result_passed_filter_reads"),
        }

    bowtie2_data = (
        data
        .get("report_saved_raw_data", {})
        .get("multiqc_bowtie2", {})
    )
    sample_bowtie2 = bowtie2_data.get(sample_name, {})
    if sample_bowtie2:
        stats["bowtie2"] = {
            "num_human_reads": sample_bowtie2.get("reads_aligned"),
        }

    return stats