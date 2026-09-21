# app/taxonomy_utils.py
#
# Shared read-count maths for classifier profiles.
# Extracted here so routers and future services share a single implementation.
#
# Mirrors frontend/src/utils/readTotals.ts — same rules and same field names,
# so the API and the taxonomy table cannot disagree about what a sample holds.
# Change one, change the other.

from dataclasses import dataclass
from typing import Optional

from app.constants import TAXON_ID_HUMAN, TAXON_ID_UNCLASSIFIED


@dataclass(frozen=True)
class ReadTotals:
    """Read counts for one classifier profile."""

    # Reads the classifier placed on some taxon.
    classified: float
    # Reads the classifier could not place (taxon 0).
    unclassified: float
    # Everything the classifier processed: classified + unclassified.
    total: float
    # Reads assigned directly to Homo sapiens.
    host: float
    # Denominator for per-taxon percentages: classified minus host.
    non_host: float
    # True when host reads exceed the classified total, which cannot happen in
    # consistent data. Callers log it with the sample they were reading.
    host_exceeds_classified: bool

    @property
    def host_pct(self) -> Optional[float]:
        """Host reads as a percentage of everything the classifier processed.

        The denominator is `total`, not `classified`, so the figure is
        comparable between samples regardless of how much of a run was
        classified. None when nothing was processed.
        """
        if not self.total:
            return None
        return round(self.host / self.total * 100, 1)


def read_totals(entries: list[dict], clf_qc: Optional[dict] = None) -> ReadTotals:
    """Return the read totals for one classifier profile.

    Taxpasta profiles hold DIRECT counts — reads assigned exactly to a taxon,
    not to it and everything below it (see ``CladeCell.direct`` in
    app/models/clade.py). Root therefore holds only the reads that could not be
    placed any deeper, and is NOT a stand-in for the classified total: in real
    Kraken2 output a single family routinely carries more reads than root.

    ``classified`` and ``unclassified`` prefer the QC metrics when present,
    since MultiQC counts the same reads the classifier reported, and fall back
    to the profile otherwise. The two agree in practice — a classifier's
    unclassified count is the same number taxpasta writes on taxon 0.

    ``non_host`` subtracts only direct Homo sapiens reads. Host reads sitting
    on ancestor taxa (Homo, Hominidae, ...) cannot be attributed without
    lineage, which the profile does not carry; in practice Kraken2 places human
    reads on 9606 itself. It is clamped at zero, with the shortfall reported in
    ``host_exceeds_classified`` rather than passed on as a negative count.
    """
    host = 0.0
    profile_classified = 0.0
    profile_unclassified = 0.0

    for entry in entries:
        value = entry.get("abundance") or 0
        if entry.get("taxon_id") == TAXON_ID_UNCLASSIFIED:
            profile_unclassified += value
            continue
        # Entries named "unclassified <taxon>" are real NCBI taxa holding
        # placed reads, so they count here — only taxon 0 is truly unplaced.
        profile_classified += value
        if entry.get("taxon_id") == TAXON_ID_HUMAN:
            host += value

    qc = clf_qc or {}
    classified = qc.get("classified_reads")
    if classified is None:
        classified = profile_classified
    unclassified = qc.get("unclassified_reads")
    if unclassified is None:
        unclassified = profile_unclassified

    return ReadTotals(
        classified=classified,
        unclassified=unclassified,
        total=classified + unclassified,
        host=host,
        non_host=max(0.0, classified - host),
        host_exceeds_classified=host > classified,
    )
