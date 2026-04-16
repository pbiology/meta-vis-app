# app/ingestor/multiqc_reader.py

import json
from pathlib import Path

from app.ingestor.models import MultiQCRaw


def read_multiqc(file_path: str) -> MultiQCRaw:
    """
    Parse the multiqc_data.json and return all raw data keyed by tool.

    Returns a MultiQCRaw with keys: kraken2, centrifuge, fastqc, fastp, bowtie2
    each containing a dict of sample_name -> stats.
    The orchestrator extracts per-sample data using _extract_base_qc() and
    _extract_classifier_qc().
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"MultiQC file not found: {file_path}")

    with open(path) as f:
        data: dict = json.load(f)

    raw: dict = data.get("report_saved_raw_data", {})

    return MultiQCRaw(
        kraken2=raw.get("multiqc_kraken", {}),
        centrifuge=raw.get("multiqc_centrifuge_centrifuge", {}),
        diamond=raw.get("diamond", {}),
        fastqc=raw.get("multiqc_fastqc", {}),
        fastp=raw.get("multiqc_fastp", {}),
        bowtie2=raw.get("multiqc_bowtie2", {}),
    )
