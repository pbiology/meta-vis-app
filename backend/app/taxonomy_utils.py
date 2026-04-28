# app/taxonomy_utils.py
#
# Shared helpers for non-host read calculations.
# Extracted here so routers and future services share a single implementation.

from typing import Optional

from app.constants import HOST_TAXON_IDS


def non_host_total(entries: list, clf_qc: Optional[dict] = None) -> float:
    """Return the total non-host read count for a classifier profile.

    Priority order:
    1. classified_reads from QC metrics minus Homo sapiens reads (most accurate).
    2. Root-node reads minus Homo sapiens reads (Kraken2 fallback).
    3. Sum of all entries excluding HOST_TAXON_IDS and unclassified labels.
    """
    host_reads = next((e["abundance"] for e in entries if e.get("taxon_id") == 9606), 0)
    if clf_qc and clf_qc.get("classified_reads") is not None:
        return clf_qc["classified_reads"] - host_reads
    root_reads = next((e["abundance"] for e in entries if e.get("taxon_id") == 1), 0)
    if root_reads:
        return root_reads - host_reads
    return sum(
        e["abundance"]
        for e in entries
        if e.get("taxon_id") not in HOST_TAXON_IDS
        and e.get("name") != "unclassified"
        and not (e.get("name") or "").startswith("unclassified ")
    )


def host_pct_for(entries: list, clf_qc: Optional[dict] = None) -> Optional[float]:
    """Return the percentage of reads that are host (Homo sapiens), or None if unknown."""
    host_reads = next((e["abundance"] for e in entries if e.get("taxon_id") == 9606), 0)
    classified_reads = clf_qc.get("classified_reads") if clf_qc else None
    if classified_reads is None:
        classified_reads = next(
            (e["abundance"] for e in entries if e.get("taxon_id") == 1), 0
        )
    total_reads = (
        host_reads + (clf_qc.get("unclassified_reads") or 0)
        if clf_qc
        else classified_reads
    )
    if not total_reads:
        return None
    return round(host_reads / total_reads * 100, 1)
