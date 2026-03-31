# app/ingestor/taxpasta_reader.py

import pandas as pd
from pathlib import Path
from typing import Optional


# Superkingdom names as they appear in the lineage string
SUPERKINGDOM_NAMES = {
    "Bacteria", "Archaea", "Eukaryota", "Viruses",
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


def read_taxpasta(
    file_path: str,
    sample_column: str,
    superkingdom_map: Optional[dict] = None,  # kept for API compatibility, no longer used
) -> list[dict]:
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

    if sample_column not in df.columns:
        raise ValueError(
            f"Sample column '{sample_column}' not found in TAXPASTA file. "
            f"Available columns: {list(df.columns)}"
        )

    has_lineage = "lineage" in df.columns

    df = df.rename(columns={
        "taxonomy_id": "taxon_id",
        sample_column: "abundance",
    })

    df["taxon_id"] = pd.to_numeric(df["taxon_id"], errors="coerce").fillna(0).astype(int)
    df["abundance"] = pd.to_numeric(df["abundance"], errors="coerce").fillna(0.0)
    df = df[df["abundance"] > 0]
    df = df[df["abundance"].apply(lambda x: isinstance(x, (int, float)) and x == x and x != float('inf'))].copy()

    records = []
    for row in df.itertuples(index=False):
        taxon_id   = int(row.taxon_id)
        name       = row.name if row.name and not pd.isna(row.name) else str(taxon_id)
        lineage    = getattr(row, "lineage", None) if has_lineage else None
        superkingdom = _superkingdom_from_lineage(lineage)
        rank_val = getattr(row, "rank", None) if "rank" in df.columns else None
        if rank_val is not None and (not isinstance(rank_val, str)) and pd.isna(rank_val):
            rank_val = None
        records.append({
            "taxon_id": taxon_id,
            "name": name,
            "rank": rank_val,
            "abundance": float(row.abundance),
            "superkingdom": superkingdom,
        })

    return records