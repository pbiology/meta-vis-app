# app/ingestor/taxpasta_reader.py

import pandas as pd
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# NCBI taxonomy helpers
# ---------------------------------------------------------------------------

SUPERKINGDOM_TAXIDS = {2, 2157, 2759, 10239}
SUPERKINGDOM_NAMES = {
    2:     "Bacteria",
    2157:  "Archaea",
    2759:  "Eukaryota",
    10239: "Viruses",
}


def load_nodes(nodes_dmp_path: str) -> dict[int, tuple[int, str]]:
    """
    Parse a nodes.dmp file and return a dict mapping taxon_id -> (parent_id, rank).
    Only loads taxon_id, parent_id, and rank — fast enough for the full NCBI dump.
    """
    nodes: dict[int, tuple[int, str]] = {}
    path = Path(nodes_dmp_path)

    if not path.exists():
        raise FileNotFoundError(f"nodes.dmp not found at: {nodes_dmp_path}")

    with open(path) as fh:
        for line in fh:
            parts = line.split("\t|\t")
            taxon_id  = int(parts[0].strip())
            parent_id = int(parts[1].strip())
            rank      = parts[2].strip()
            nodes[taxon_id] = (parent_id, rank)

    return nodes


def resolve_superkingdom(
    taxon_id: int,
    nodes: dict[int, tuple[int, str]],
) -> Optional[str]:
    """
    Walk up the taxonomy tree from taxon_id until a superkingdom node is found.
    Returns the superkingdom name string, or None if not resolvable.
    """
    visited: set[int] = set()
    current = taxon_id

    while current not in visited:
        if current in SUPERKINGDOM_TAXIDS:
            return SUPERKINGDOM_NAMES[current]

        if current not in nodes:
            return None

        parent_id, _ = nodes[current]

        # Root of tree: node is its own parent (taxon_id 1 = root)
        if parent_id == current:
            return None

        visited.add(current)
        current = parent_id

    return None  # cycle guard


# ---------------------------------------------------------------------------
# Main reader
# ---------------------------------------------------------------------------

def read_taxpasta(
    file_path: str,
    sample_column: str,
    nodes_data: Optional[str] = None,
) -> list[dict]:
    """
    Read a TAXPASTA TSV file and return a list of taxon entry dicts.

    Args:
        file_path:     Absolute path to the TAXPASTA TSV file.
        sample_column: Column name in the TSV corresponding to this sample's
                       read counts (e.g. "PE-04-28_k2_pluspf.kraken2.kraken2.report").
        nodes_data:    Optional absolute path to an NCBI taxonomy nodes.dmp file.
                       When provided, each entry will include a resolved
                       'superkingdom' value (Bacteria | Archaea | Eukaryota | Viruses).
                       When omitted, 'superkingdom' is stored as None.
    """
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

    if sample_column not in df.columns:
        raise Va