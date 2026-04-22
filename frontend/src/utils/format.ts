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
