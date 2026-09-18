export function fmt(n: number | string | null | undefined, decimals = 0): string {
  if (n === undefined || n === null) return "—";
  return typeof n === "number"
    ? n.toLocaleString(undefined, { maximumFractionDigits: decimals })
    : n;
}

export function fmtPct(n: number | null | undefined, decimals = 1): string {
  if (n === undefined || n === null) return "—";
  return `${n.toFixed(decimals)}%`;
}

/**
 * ISO timestamp → local calendar date, e.g. "2026-09-18".
 *
 * The sv-SE locale is what renders it YYYY-MM-DD, so ingest timestamps line up
 * with the plain `order_date` strings shown beside them. Local time, not UTC:
 * an ingest at 23:30 UTC belongs to the day the operator saw it happen.
 */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString("sv-SE");
}
