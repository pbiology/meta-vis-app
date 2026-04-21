export function fmt(n, decimals = 0) {
  if (n === undefined || n === null) return "—";
  return typeof n === "number"
    ? n.toLocaleString(undefined, { maximumFractionDigits: decimals })
    : n;
}

export function fmtPct(n, decimals = 1) {
  if (n === undefined || n === null) return "—";
  return `${n.toFixed(decimals)}%`;
}
