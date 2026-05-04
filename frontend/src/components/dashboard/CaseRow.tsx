import { SignalDot, type SignalKind } from "../SignalPill";
import type { CaseListItem } from "../../api/types";

interface CaseRowProps {
  c: CaseListItem;
  signals: SignalKind[];
  dense?: boolean;
}

function relDay(s: string | null | undefined): string {
  if (!s) return "—";
  const d = new Date(s);
  const days = Math.round((Date.now() - d.getTime()) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// Renders one case as a clickable row that opens the case-centric view in a NEW tab.
// The dashboard never navigates the current tab to a case — the user keeps the
// dashboard open as their work surface and switches tabs to focus on a case.
export default function CaseRow({ c, signals, dense = false }: Readonly<CaseRowProps>) {
  const reviewed = c.review?.reviewed ?? false;
  const sampleCount = c.sample_count ?? 0;
  const analysis = c.analysis_type ?? "—";

  return (
    <a
      href={`/case/${c.case_id}`}
      target="_blank"
      rel="noopener noreferrer"
      className={`grid items-center gap-3 border-b border-gray-50 hover:bg-gray-50 transition-colors no-underline ${
        dense ? "px-3 py-1.5" : "px-3.5 py-2.5"
      }`}
      style={{ gridTemplateColumns: "10px 110px 1fr auto auto auto" }}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${reviewed ? "bg-green-600" : "bg-amber-600"}`}
        title={reviewed ? "Reviewed" : "Pending"}
      />
      <span className="font-mono text-xs font-medium text-gray-900 truncate">{c.case_id}</span>
      <div className="flex items-center gap-1.5 min-w-0">
        {signals.map((s) => (
          <SignalDot key={s} kind={s} />
        ))}
        <span className="text-[11px] text-gray-500 capitalize truncate">{analysis}</span>
      </div>
      <span className="text-[11px] text-gray-500 font-mono">{sampleCount} smpl</span>
      <span className="text-[11px] text-gray-400">{relDay(c.order_date)}</span>
      <svg className="w-3 h-3 text-gray-300" viewBox="0 0 12 12" fill="none">
        <path
          d="M3 9L9 3M9 3H4M9 3v5"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </a>
  );
}
