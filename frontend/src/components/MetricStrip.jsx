/**
 * A single horizontal strip where each metric is separated by hairline dividers.
 *
 * @param {{ label: string, value: string, sub?: string, warn?: boolean }[]} metrics
 */
export function MetricStrip({ metrics }) {
  return (
    <div className="flex bg-white border border-gray-200 rounded-lg overflow-hidden">
      {metrics.map((m, i) => (
        <div
          key={i}
          className={`
            flex flex-col gap-0.5 flex-1 px-3.5 py-2.5
            ${i < metrics.length - 1 ? "border-r border-gray-100" : ""}
          `}
        >
          <span className="text-[10px] font-medium uppercase tracking-wide text-gray-400">
            {m.label}
          </span>
          <span
            className={`font-mono font-medium leading-none ${m.warn ? "text-amber-600" : "text-gray-900"}`}
            style={{ fontSize: 14 }}
          >
            {m.value ?? "—"}
          </span>
          {m.sub && <span className="text-[10px] text-gray-400">{m.sub}</span>}
        </div>
      ))}
    </div>
  );
}
