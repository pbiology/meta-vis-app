# app/ingestor/emu_reader.py

"""Parse per-sample Emu rel-abundance TSV files into TaxonEntry records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.models.taxonomy import TaxonEntry

# Rows with these tax_id values are Emu bookkeeping, not real taxa.
_SKIP_TAX_IDS = {"unmapped", "mapped_unclassified"}


def read_emu_abundance(file_path: str) -> list[TaxonEntry]:
    """Parse an Emu ``*_rel-abundance.tsv`` into a list of TaxonEntry.

    Filters out ``unmapped`` / ``mapped_unclassified`` rows and any row
    with zero abundance.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Emu abundance file not found: {file_path}")

    df = pd.read_csv(path, sep="\t", dtype={"tax_id": str})

    required = {"tax_id", "abundance"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Emu abundance file '{file_path}' is missing required columns: {missing}"
        )

    entries: list[TaxonEntry] = []
    for _, row in df.iterrows():
        raw_tax_id = str(row["tax_id"]).strip()
        if raw_tax_id in _SKIP_TAX_IDS:
            continue

        try:
            taxon_id = int(raw_tax_id)
        except ValueError:
            continue

        abundance = float(row["abundance"])
        if abundance <= 0:
            continue

        name = _resolve_name(row)
        rank = _resolve_rank(row)
        superkingdom = (
            str(row["superkingdom"]).strip()
            if "superkingdom" in row.index and pd.notna(row.get("superkingdom"))
            else None
        )

        entries.append(
            TaxonEntry(
                taxon_id=taxon_id,
                name=name,
                rank=rank,
                abundance=abundance,
                superkingdom=superkingdom,
            )
        )

    return entries


# Column preference order: most specific → least specific.
_RANK_COLUMNS = [
    "subspecies",
    "species subgroup",
    "species group",
    "species",
    "genus",
    "family",
    "order",
    "class",
    "phylum",
    "superkingdom",
]


def _resolve_name(row: "pd.Series[Any]") -> str:
    """Return the most specific non-empty taxonomic name for the row."""
    for col in _RANK_COLUMNS:
        if col in row.index and pd.notna(row[col]) and str(row[col]).strip():
            return str(row[col]).strip()
    return f"taxon_{row['tax_id']}"


def _resolve_rank(row: "pd.Series[Any]") -> str:
    """Return the rank corresponding to the most specific non-empty column."""
    for col in _RANK_COLUMNS:
        if col in row.index and pd.notna(row[col]) and str(row[col]).strip():
            return col
    return "unknown"
