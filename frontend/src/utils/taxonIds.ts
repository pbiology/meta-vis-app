export interface ParsedTaxonIds {
  /** Distinct positive integer ids, in first-seen order. */
  ids: number[];
  /** Tokens that are not a positive integer, as typed — shown back to the user. */
  invalid: string[];
}

/**
 * Parse pasted taxon ids separated by commas, semicolons, whitespace or
 * newlines — a typed list or a column copied from a spreadsheet.
 *
 * Nothing is dropped silently: every token is either an id or listed in
 * `invalid`.
 */
export function parseTaxonIds(text: string): ParsedTaxonIds {
  const ids: number[] = [];
  const seen = new Set<number>();
  const invalid: string[] = [];
  for (const token of text.split(/[\s,;]+/)) {
    if (token === "") continue;
    if (!/^\d+$/.test(token) || Number(token) < 1 || !Number.isSafeInteger(Number(token))) {
      invalid.push(token);
      continue;
    }
    const id = Number(token);
    if (!seen.has(id)) {
      seen.add(id);
      ids.push(id);
    }
  }
  return { ids, invalid };
}
