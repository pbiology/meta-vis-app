# app/ingestor/nanoplot_reader.py

"""Parse NanoPlot NanoStats.txt files into structured QC metrics."""

from pathlib import Path
from typing import Any

from app.ingestor.models import NanoPlotStats

# Maps NanoStats.txt keys (lowercased) to NanoPlotStats field names.
_KEY_MAP: dict[str, str] = {
    "mean read length": "mean_read_length",
    "mean read quality": "mean_read_quality",
    "median read length": "median_read_length",
    "median read quality": "median_read_quality",
    "number of reads": "number_of_reads",
    "read length n50": "read_length_n50",
    "total bases": "total_bases",
}

# Fields that should be stored as int rather than float.
_INT_FIELDS = {"number_of_reads", "read_length_n50", "total_bases"}


def read_nanostats(file_path: str) -> NanoPlotStats:
    """Parse a NanoPlot ``NanoStats.txt`` file into :class:`NanoPlotStats`."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"NanoStats file not found: {file_path}")

    parsed: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key_part, _, val_part = line.partition(":")
        key = key_part.strip().lower()
        if key not in _KEY_MAP:
            continue

        field = _KEY_MAP[key]
        raw = val_part.strip().replace(",", "")
        try:
            num = float(raw)
        except ValueError:
            continue

        if field in _INT_FIELDS:
            parsed[field] = int(num)
        else:
            parsed[field] = num

    return NanoPlotStats(**parsed)
