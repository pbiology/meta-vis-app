import pandas as pd
from pathlib import Path


def read_taxpasta(file_path: str, classifier: str) -> list[dict]:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"TAXPASTA file not found: {file_path}")

    df = pd.read_csv(path, sep="\t")

    expected_columns = {"taxonomy_id", "taxonomy_lvl", "name"}
    if not expected_columns.issubset(df.columns):
        raise ValueError(
            f"Unexpected TAXPASTA format. Expected columns: {expected_columns}. "
            f"Got: {set(df.columns)}"
        )

    abundance_col = [c for c in df.columns if c not in expected_columns]
    if len(abundance_col) != 1:
        raise ValueError(
            f"Expected exactly one abundance column, found: {abundance_col}"
        )

    df = df.rename(columns={
        "taxonomy_id": "taxon_id",
        "taxonomy_lvl": "rank",
        abundance_col[0]: "abundance",
    })

    df["taxon_id"] = pd.to_numeric(df["taxon_id"], errors="coerce").fillna(0).astype(int)
    df["abundance"] = pd.to_numeric(df["abundance"], errors="coerce").fillna(0.0)
    df = df[df["abundance"] > 0]

    return df[["taxon_id", "name", "rank", "abundance"]].to_dict("records")