# app/ingestor/multiqc_reader.py

import json
from pathlib import Path


def read_multiqc(file_path: str) -> dict:
    """
    Parse the multiqc_data.json and return all raw data keyed by tool.
    Returns a dict with keys: kraken2, fastqc, fastp, bowtie2
    each containing a dict of sample_name -> stats.
    The orchestrator extracts per-sample data using extract_sample_qc().
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"MultiQC file not found: {file_path}")

    with open(path) as f:
        data = json.load(f)

    raw = data.get("report_saved_raw_data", {})

    return {
        "kraken2": raw.get("multiqc_kraken", {}),
        "fastqc":  raw.get("multiqc_fastqc", {}),
        "fastp":   raw.get("multiqc_fastp", {}),
        "bowtie2": raw.get("multiqc_bowtie2", {}),
    }