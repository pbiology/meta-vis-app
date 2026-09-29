/**
 * Display filters: hide the taxa on a user's active filter lists from the
 * taxonomy table. Display only — callers apply this after computing read
 * totals, so hiding a taxon never changes classified or non-host counts.
 */

export interface DisplayFilterResult<T> {
  visible: T[];
  /** Entries removed from view. */
  hiddenCount: number;
  /** Entries on a filter list that were kept because they are protected. */
  protectedCount: number;
}

/**
 * Remove entries whose `taxon_id` is in `hiddenIds`, except those in
 * `protectedIds` (known pathogens), which are always kept visible.
 * Exact id matching: a filtered genus does not hide its species.
 */
export function applyDisplayFilters<T extends { taxon_id: number }>(
  entries: T[],
  hiddenIds: ReadonlySet<number>,
  protectedIds: ReadonlySet<number> = new Set()
): DisplayFilterResult<T> {
  if (hiddenIds.size === 0) return { visible: entries, hiddenCount: 0, protectedCount: 0 };

  const visible: T[] = [];
  let hiddenCount = 0;
  let protectedCount = 0;
  for (const entry of entries) {
    if (!hiddenIds.has(entry.taxon_id)) {
      visible.push(entry);
    } else if (protectedIds.has(entry.taxon_id)) {
      protectedCount += 1;
      visible.push(entry);
    } else {
      hiddenCount += 1;
    }
  }
  return { visible, hiddenCount, protectedCount };
}
