# app/ingestor/taxpasta_reader.py

import pandas as pd
from pathlib import Path
from typing import Optional

from app.models.taxonomy import TaxonEntry


# Superkingdom names as they appear in the lineage string
SUPERKINGDOM_NAMES = {
    "Bacteria",
    "Archaea",
    "Eukaryota",
    "Viruses",
}


def _superkingdom_from_lineage(lineage: str) -> Optional[str]:
    """Extract superkingdom from a lineage string like 'Bacteria;Firmicutes;...'"""
    if not lineage or pd.isna(lineage):
        return None
    parts = [p.strip() for p in str(lineage).split(";")]
    for part in parts:
        if part in SUPERKINGDOM_NAMES:
            return part
    return None


def load_taxpasta(file_path: str) -> pd.DataFrame:
    """Read and validate a taxpasta TSV, returning a normalised DataFrame.

    Renames ``taxonomy_id`` → ``taxon_id`` and coerces the taxon_id column to
    int.  Sample-abundance columns are left as-is so that
    ``extract_sample_profile`` can slice any sample on demand without
    re-reading the file.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"TAXPASTA file not found: {file_path}")

    df = pd.read_csv(path, sep="\t")

    required = {"taxonomy_id", "name"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"TAXPASTA file missing required columns: {missing}. Got: {set(df.columns)}"
        )

    df = df.rename(columns={"taxonomy_id": "taxon_id"})
    df["taxon_id"] = (
        pd.to_numeric(df["taxon_id"], errors="coerce").fillna(0).astype(int)
    )

    return df


def extract_sample_profile(df: pd.DataFrame, sample_column: str) -> list[TaxonEntry]:
    """Build a list of TaxonEntry from a pre-loaded taxpasta DataFrame.

    Slices *sample_column*, filters zero/invalid abundances, and converts each
    row to a ``TaxonEntry``.  Call ``load_taxpasta`` first to obtain *df*.
    """
    if sample_column not in df.columns:
        raise ValueError(
            f"Sample column '{sample_column}' not found in TAXPASTA file. "
            f"Available columns: {list(df.columns)}"
        )

    has_lineage = "lineage" in df.columns

    cols = ["taxon_id", "name"]
    if "rank" in df.columns:
        cols.append("rank")
    if has_lineage:
        cols.append("lineage")
    cols.append(sample_column)

    work = df[cols].copy()
    work = work.rename(columns={sample_column: "abundance"})
    work["abundance"] = pd.to_numeric(work["abundance"], errors="coerce").fillna(0.0)
    work = work[work["abundance"] > 0]
    work = work[
        work["abundance"].apply(
            lambda x: isinstance(x, (int, float)) and x == x and x != float("inf")
        )
    ]

    records: list[TaxonEntry] = []
    for row in work.itertuples(index=False):
        taxon_id = int(row.taxon_id)  # type: ignore[arg-type]
        raw_name = getattr(row, "name", None)
        name: str = (
            str(raw_name) if raw_name and not pd.isna(raw_name) else str(taxon_id)
        )
        lineage = getattr(row, "lineage", None) if has_lineage else None
        superkingdom = (
            _superkingdom_from_lineage(lineage) if isinstance(lineage, str) else None
        )
        rank_val = getattr(row, "rank", None) if "rank" in work.columns else None
        if (
            rank_val is not None
            and (not isinstance(rank_val, str))
            and pd.isna(rank_val)
        ):
            rank_val = None
        if isinstance(rank_val, str):
            rank_val = rank_val.lower()
        records.append(
            TaxonEntry(
                taxon_id=taxon_id,
                name=name,
                rank=rank_val,
                abundance=float(row.abundance),  # type: ignore[arg-type]
                superkingdom=superkingdom,
            )
        )

    return records


def read_taxpasta(file_path: str, sample_column: str) -> list[TaxonEntry]:
    """Convenience wrapper: load file and extract one sample profile.

    Kept for backward compatibility and tests.  When ingesting multiple samples
    from the same file, prefer calling ``load_taxpasta`` once and then
    ``extract_sample_profile`` for each sample.
    """
    return extract_sample_profile(load_taxpasta(file_path), sample_column)
