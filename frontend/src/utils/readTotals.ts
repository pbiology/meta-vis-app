import { TAXON_ID_HUMAN, TAXON_ID_UNCLASSIFIED } from "./taxonomy";
import type { SampleProfileEntry } from "../api/types";

// The QC fields this calculation needs. Kept structural so any classifier QC
// object can be passed without being widened first.
export interface ReadTotalsQc {
  classified_reads?: number;
}

export interface ReadTotals {
  // Reads the classifier placed on some taxon. From QC when available,
  // otherwise summed from the profile.
  classified: number;
  // Reads the classifier could not place (taxon 0).
  unclassified: number;
  // Everything the classifier processed: classified + unclassified.
  total: number;
  // Denominator for per-taxon percentages: classified minus host.
  nonHost: number;
  // True when host reads exceed the classified total, which cannot happen in
  // consistent data — the caller should surface this rather than hide it.
  hostExceedsClassified: boolean;
}

/**
 * Read totals for one classifier profile.
 *
 * Taxpasta profiles hold DIRECT counts — reads assigned exactly to a taxon,
 * not to it and everything below it (see `CladeCell.direct` in
 * app/models/clade.py). Root (taxon 1) therefore holds only the reads that
 * could not be placed any deeper, and is NOT a stand-in for the classified
 * total: in real Kraken2 output a single family routinely carries more reads
 * than root does.
 *
 * `total` matches app/clade/tree.py::column_signal — every row, unclassified
 * included — so the table header and the clade view agree on what the
 * classifier processed.
 *
 * `nonHost` subtracts only direct Homo sapiens reads. Host reads sitting on
 * ancestor taxa (Homo, Hominidae, …) cannot be attributed without lineage,
 * which the profile does not carry; in practice Kraken2 places human reads on
 * 9606 itself. Note this is a different denominator from the clade view's
 * reads-per-million, which divides by `total` so that a mostly-unclassified
 * sample does not look enriched.
 */
export function readTotals(
  entries: readonly SampleProfileEntry[],
  clfQc?: ReadTotalsQc | null
): ReadTotals {
  let host = 0;
  let unclassified = 0;
  let profileClassified = 0;

  for (const e of entries) {
    const value = e.abundance ?? 0;
    if (e.taxon_id === TAXON_ID_UNCLASSIFIED) {
      unclassified += value;
      continue;
    }
    // Rows named "unclassified <taxon>" are real NCBI taxa holding classified
    // reads, so they stay in the total — only taxon 0 is truly unplaced.
    profileClassified += value;
    if (e.taxon_id === TAXON_ID_HUMAN) host += value;
  }

  const classified = clfQc?.classified_reads ?? profileClassified;

  return {
    classified,
    unclassified,
    total: unclassified + classified,
    nonHost: Math.max(0, classified - host),
    hostExceedsClassified: host > classified,
  };
}
