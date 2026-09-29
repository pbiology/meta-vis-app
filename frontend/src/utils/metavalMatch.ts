/**
 * Placing metaval results in the taxonomy table. A result is shown as a pill
 * on its taxon's row; one without a row is listed apart, so a metaval result
 * is never silently dropped.
 */
import type { MetavalSummary } from "../api/types";

/** Metaval results produced from one classifier's hits. */
export function metavalForClassifier(
  results: readonly MetavalSummary[],
  classifier: string
): MetavalSummary[] {
  return results.filter((r) => r.classifier === classifier);
}

/** Results keyed by taxon id; results with an unresolved taxon are skipped. */
export function metavalByTaxon(results: readonly MetavalSummary[]): Map<number, MetavalSummary> {
  const byTaxon = new Map<number, MetavalSummary>();
  for (const r of results) {
    if (r.taxon_id != null) byTaxon.set(r.taxon_id, r);
  }
  return byTaxon;
}

/**
 * Results with no row in the taxonomy table: the taxon was never resolved
 * (old-format metaval output), or it is not among the table's listed taxa.
 */
export function unmatchedMetaval(
  results: readonly MetavalSummary[],
  listedTaxonIds: ReadonlySet<number>
): MetavalSummary[] {
  return results.filter((r) => r.taxon_id == null || !listedTaxonIds.has(r.taxon_id));
}
