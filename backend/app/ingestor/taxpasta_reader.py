# app/ingestor/taxpasta_reader.py

import pandas as pd
from pathlib import Path
from typing import Optional


def name_from_lineage(lineage: str) -> str:
    """
    Extract a display name from a lineage string by taking the last element.
    e.g. "cellular organisms;Eukaryota;Opisthokonta" -> "Opisthokonta"
    Empty lineage (unclassified reads) returns "unclassified".
    """
    if not lineage or pd.isna(lineage):
        return "unclassified"
    parts = [p.strip() for p in str(lineage).split(";")]
    return parts[-1] if parts[-1] else "unclassified"


def read_taxpasta(
    file_path: str,
    sample_column: str,
    superkingdom_map: Optional[dict] = None,
) -> list[dict]:
    """
    Read a TAXPASTA TSV file and return a list of taxon entry dicts.

    Args:
        file_path:        Absolute path to the TAXPASTA TSV file.
        sample_column:    Column name corresponding to this sample's read counts.
        superkingdom_map: Optional dict of taxon_id -> superkingdom string,
                          preloaded from the taxonomy_nodes collection.
                          When omitted, 'superkingdom' is stored as None.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"TAXPASTA file not found: {file_path}")

    df = pd.read_csv(path, sep="\t")

    if "taxonomy_id" not in df.columns or "lineage" not in df.columns:
        raise ValueError(
            f"Unexpected TAXPASTA format. Expected 'taxonomy_id' and 'lineage' columns. "
            f"Got: {set(df.columns)}"
        )

    if sample_column not in df.columns:
        raise ValueError(
            f"Sample column '{sample_column}' not found in TAXPASTA file. "
            f"Available columns: {list(df.columns)}"
        )

    df = df.rename(columns={
        "taxonomy_id": "taxon_id",
        sample_column: "abundance",
    })

    df["taxon_id"]  = pd.to_numeric(df["taxon_id"],  errors="coerce").fillna(0).astype(int)
    df["abundance"] = pd.to_numeric(df["abundance"], errors="coerce").fillna(0.0)
    df = df[df["abundance"] > 0].copy()

    records = []
    for row in df[["taxon_id", "lineage", "abundance"]].itertuples(index=False):
        taxon_id = int(row.taxon_id)
        entry = {
            "taxon_id":     taxon_id,
            "name":         name_from_lineage(row.lineage),
            "rank":         None,
            "abundance":    float(row.abundance),
            "superkingdom": superkingdom_map.get(taxon_id) if superkingdom_map else None,
        }
        records.append(entry)

    return records