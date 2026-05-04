import { Link } from "react-router-dom";
import Badge from "../Badge";
import SignalPill, { type SignalKind } from "../SignalPill";

interface CaseTopBarProps {
  caseId: string;
  signals: SignalKind[];
  reviewed: boolean;
  reviewer?: string | null;
  ticketId?: string | null;
  ticketUrl?: string | null;
  onReview: () => void;
  onUnreviewRequest: () => void;
  reviewing: boolean;
  canReview: boolean;
}

// Top bar shown above the case-specific sidebar. Mimics the design's breadcrumb
// + monospaced case_id + signals + action buttons row, but sources the case
// state from the live data rather than the design's mock.
export default function CaseTopBar({
  caseId,
  signals,
  reviewed,
  reviewer,
  ticketId,
  ticketUrl,
  onReview,
  onUnreviewRequest,
  reviewing,
  canReview,
}: Readonly<CaseTopBarProps>) {
  return (
    <header className="bg-white border-b border-gray-100 px-6 py-3 flex items-center gap-3 flex-shrink-0">
      <Link
        to="/"
        className="flex items-center gap-1 text-[11px] text-gray-500 hover:text-gray-800 transition-colors no-underline"
      >
        <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
          <path
            d="M10 3L5 8l5 5"
            stroke="currentColor"
            strokeWidth="1.5"
            fill="none"
            strokeLinecap="round"
          />
        </svg>
        Dashboard
      </Link>
      <span className="text-gray-200">/</span>
      <span className="text-[11px] text-gray-500">Case</span>
      <h1 className="font-mono text-sm font-semibold text-gray-900 m-0">{caseId}</h1>
      {ticketId &&
        (ticketUrl ? (
          <a
            href={ticketUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] text-blue-600 hover:underline"
            title="Open Freshdesk ticket"
          >
            #{ticketId}
          </a>
        ) : (
          <span className="text-[11px] text-gray-400">#{ticketId}</span>
        ))}
      {signals.map((s) => (
        <SignalPill key={s} kind={s} />
      ))}
      <Badge type={reviewed ? "reviewed" : "pending"} />
      <div className="ml-auto flex gap-2">
        {!reviewed && canReview && (
          <button
            onClick={onReview}
            disabled={reviewing}
            className="px-3 py-1.5 text-xs rounded-md border-0 bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-50 transition-colors"
          >
            {reviewing ? "Saving…" : "Mark reviewed ✓"}
          </button>
        )}
        {reviewed && (
          <button
            onClick={onUnreviewRequest}
            className="px-3 py-1.5 text-xs rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 transition-colors"
          >
            ● Reviewed by {reviewer ?? "—"}
          </button>
        )}
      </div>
    </header>
  );
}
