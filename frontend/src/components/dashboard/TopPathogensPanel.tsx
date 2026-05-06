import { TOP_PATHOGENS_14D } from "./mockData";

export default function TopPathogensPanel() {
  return (
    <div className="bg-white border border-gray-100 rounded-lg p-4 flex flex-col">
      <div className="flex items-baseline gap-2 mb-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900">
          Top pathogens · 14d
        </h3>
        <span
          className="text-[10px] text-amber-700 font-medium"
          title="Backed by mock data — TODO(backend)"
        >
          demo
        </span>
      </div>
      <div className="flex flex-col gap-2">
        {TOP_PATHOGENS_14D.map((p) => (
          <div key={p.name} className="flex items-center gap-2">
            <span className="text-xs italic text-gray-800 flex-1 min-w-0 truncate">{p.name}</span>
            <span className="font-mono text-xs font-medium text-gray-900">{p.count}</span>
            <span className="text-[10px] text-gray-400 w-16 text-right">{p.last}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
