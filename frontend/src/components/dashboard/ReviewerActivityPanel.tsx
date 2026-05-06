import { REVIEWER_LEADERBOARD } from "./mockData";

export default function ReviewerActivityPanel() {
  const max = Math.max(1, ...REVIEWER_LEADERBOARD.map((r) => r.reviewed));
  return (
    <div className="bg-white border border-gray-100 rounded-lg p-4">
      <div className="flex items-baseline gap-2 mb-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900">
          Reviewer activity
        </h3>
        <span
          className="text-[10px] text-amber-700 font-medium"
          title="Backed by mock data — TODO(backend)"
        >
          demo
        </span>
      </div>
      {REVIEWER_LEADERBOARD.map((r) => {
        const pct = (r.reviewed / max) * 100;
        return (
          <div key={r.name} className="mb-2 last:mb-0">
            <div className="flex items-baseline mb-1 text-[11px]">
              <span className="text-gray-800 flex-1">{r.name}</span>
              <span className="text-gray-400 font-mono">{r.reviewed}</span>
            </div>
            <div className="h-1 bg-gray-100 rounded overflow-hidden">
              <div className="h-full bg-gray-900" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
