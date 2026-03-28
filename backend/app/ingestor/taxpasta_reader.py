import pandas as pd
from pathlib import Path


def read_taxpasta(file_path: str, column: str) -> list[dict]:
    """
    Reads a single sample's profile from a wide-format TAXPASTA TSV.
    Extracts the specified column and ignores all others.
    Taxon name is derived from the last element of the lineage string.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"TAXPASTA file not found: {file_path}")

    df = pd.read_csv(path, sep="\t")

    required_columns = {"taxonomy_id", "lineage"}
    if not required_columns.issubset(df.columns):
        raise ValueError(
            f"Unexpected TAXPASTA format. Expected columns: {required_columns}. "
            f"Got: {set(df.columns)}"
        )

    if column not in df.columns:
        available = [c for c in df.columns if c not in {"taxonomy_id", "lineage"}]
        raise ValueError(
            f"Column '{column}' not found in TAXPASTA file. "
            f"Available sample columns: {available}"
        )

    df["name"] = df["lineage"].apply(
        lambda x: x.split(";")[-1].strip() if isinstance(x, str) and x else "unclassified"
    )

    df["taxonomy_id"] = pd.to_numeric(df["taxonomy_id"], errors="coerce").fillna(0).astype(int)
    df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0)

    df = df[df[column] > 0][["taxonomy_id", "name", column]].copy()
    df = df.rename(columns={
        "taxonomy_id": "taxon_id",
        column: "abundance",
    })

    return df[["taxon_id", "name", "abundance"]].to_dict("records")