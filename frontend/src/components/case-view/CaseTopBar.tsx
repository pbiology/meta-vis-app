import { Link } from "react-router-dom";
import Badge from "../Badge";
import SignalPill, { type SignalKind } from "../SignalPill";
import CaseReportPill from "./CaseReportPill";
import CaseVersionSwitcher from "./CaseVersionSwitcher";
import type { AnalysisSummary } from "../../api/types";

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
  reportCount: number;
  onOpenReport: () => void;
  analyses?: AnalysisSummary[];
  currentVersion?: number | null;
  /** True when a newer analysis of this case exists. */
  isSuperseded?: boolean;
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
  reportCount,
  onOpenReport,
  analyses = [],
  currentVersion = null,
  isSuperseded = false,
}: Readonly<CaseTopBarProps>) {
  const latestVersion = analyses.find((a) => a.is_latest)?.version;
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
        Cases
      </Link>
      <span className="text-gray-200">/</span>
      <span className="text-[11px] text-gray-500">Case</span>
      <h1 className="font-mono text-sm font-semibold text-gray-900 m-0">{caseId}</h1>
      {currentVersion != null && (
        <CaseVersionSwitcher caseId={caseId} analyses={analyses} currentVersion={currentVersion} />
      )}
      {isSuperseded && (
        <span className="flex items-center gap-1 text-[11px] text-amber-700 bg-amber-50 border border-amber-100 rounded-md px-2 py-1">
          Superseded — a newer analysis exists
          {latestVersion != null && (
            <a
              href={`/cases/${caseId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="underline font-medium"
            >
              open v{latestVersion}
            </a>
          )}
        </span>
      )}
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
      {signals
        .filter((s) => s !== "pathogen")
        .map((s) => (
          <SignalPill key={s} kind={s} />
        ))}
      <Badge type={reviewed ? "reviewed" : "pending"} />
      <div className="ml-auto flex gap-2 items-center">
        {canReview && <CaseReportPill count={reportCount} onClick={onOpenReport} />}
        {!reviewed && canReview && (
          <button
            onClick={onReview}
            disabled={reviewing}
            className="px-3 py-1.5 text-xs rounded-md border-0 bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-50 transition-colors"
          >
            {reviewing ? "Saving…" : "Mark reviewed ✓"}
          </button>
        )}
        {reviewed && canReview && (
          <button
            onClick={onUnreviewRequest}
            className="px-3 py-1.5 text-xs rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 transition-colors"
          >
            ● Reviewed by {reviewer ?? "—"}
          </button>
        )}
        {reviewed && !canReview && (
          <span className="px-3 py-1.5 text-xs rounded-md border border-gray-200 bg-white text-gray-500">
            ● Reviewed by {reviewer ?? "—"}
          </span>
        )}
      </div>
    </header>
  );
}
