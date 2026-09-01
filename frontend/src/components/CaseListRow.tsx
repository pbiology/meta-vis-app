import Badge from "./Badge";
import type { AnalysisSummary, Case } from "../api/types";
import { analysisLabel, platformLabel } from "../lib/analysisLabels";

export interface CaseSignalSets {
  outbreak: Set<string>;
  pathogen: Set<string>;
  ntc: Set<string>;
}

interface CaseListRowProps {
  caseData: Case;
  analysis: AnalysisSummary;
  /** Total analyses of this case; drives the version badge and disclosure arrow. */
  runCount: number;
  /** Superseded rows render indented and greyed beneath their latest run. */
  superseded?: boolean;
  expanded?: boolean;
  onToggle?: () => void;
  signals: CaseSignalSets;
  ticketLinksEnabled: boolean;
  showDelete: boolean;
  onDelete: () => void;
}

function OutbreakIcon() {
  return (
    <svg className="w-3 h-3 text-amber-500 flex-shrink-0" viewBox="0 0 16 16" fill="none">
      <path d="M8 2L14 13H2L8 2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      <path d="M8 6v3M8 11v.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}

function PathogenIcon() {
  return (
    <svg className="w-3 h-3 text-red-500 flex-shrink-0" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.3" />
      <path
        d="M8 2.5v1.5M8 12v1.5M2.5 8h1.5M12 8h1.5"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
    </svg>
  );
}

function NtcIcon() {
  return (
    <svg className="w-3 h-3 text-orange-500 flex-shrink-0" viewBox="0 0 16 16" fill="none">
      <path
        d="M8 3a3 3 0 0 1 3 3v1.5h.5a1 1 0 0 1 1 1V13a1 1 0 0 1-1 1H4.5a1 1 0 0 1-1-1V8.5a1 1 0 0 1 1-1H5V6a3 3 0 0 1 3-3z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      <circle cx="8" cy="10.5" r="0.75" fill="currentColor" />
    </svg>
  );
}

export default function CaseListRow({
  caseData,
  analysis,
  runCount,
  superseded = false,
  expanded = false,
  onToggle,
  signals,
  ticketLinksEnabled,
  showDelete,
  onDelete,
}: Readonly<CaseListRowProps>) {
  const caseId = caseData.case_id;
  const hasSiblings = runCount > 1;
  // Superseded runs are addressed explicitly; the latest resolves by default.
  const href = superseded ? `/cases/${caseId}/analyses/${analysis.version}` : `/cases/${caseId}`;

  const sampleCount = analysis.sample_count ?? 0;
  const controlCount = analysis.control_count ?? 0;
  const noteCount = caseData.notes?.length ?? 0;

  return (
    <tr
      onClick={() => window.open(href, "_blank", "noopener,noreferrer")}
      className={`cursor-pointer border-b border-gray-50 transition-colors ${
        superseded ? "bg-gray-50/40 text-gray-400 hover:bg-gray-100/60" : "hover:bg-gray-50"
      }`}
    >
      <td
        className={`px-4 py-3 font-mono text-xs ${superseded ? "text-gray-400" : "text-gray-700"}`}
      >
        <div className={`flex items-center gap-1.5 ${superseded ? "pl-6" : ""}`}>
          {!superseded && hasSiblings && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggle?.();
              }}
              aria-label={expanded ? "Hide earlier analyses" : "Show earlier analyses"}
              aria-expanded={expanded}
              className="w-4 h-4 flex items-center justify-center text-gray-400 hover:text-gray-700 flex-shrink-0"
            >
              <svg
                className={`w-3 h-3 transition-transform ${expanded ? "rotate-90" : ""}`}
                viewBox="0 0 16 16"
                fill="none"
              >
                <path
                  d="M6 4l4 4-4 4"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          )}
          {!superseded && !hasSiblings && <span className="w-4 flex-shrink-0" />}
          <span>{caseId}</span>
          {/* Only superseded rows are badged. The current run is the default
              reading of a case, so labelling it adds noise; the disclosure
              arrow is what signals that earlier runs exist. */}
          {superseded && (
            <>
              <span className="px-1 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-500 flex-shrink-0">
                v{analysis.version}
              </span>
              <span className="px-1 py-0.5 rounded text-[10px] font-medium bg-amber-50 text-amber-700 flex-shrink-0">
                superseded
              </span>
            </>
          )}
          {!superseded && signals.outbreak.has(caseId) && <OutbreakIcon />}
          {!superseded && signals.pathogen.has(caseId) && <PathogenIcon />}
          {!superseded && signals.ntc.has(caseId) && <NtcIcon />}
        </div>
      </td>
      {ticketLinksEnabled && (
        <td
          className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap"
          onClick={(e) => e.stopPropagation()}
        >
          {caseData.ticket_url ? (
            <a
              href={caseData.ticket_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 hover:underline"
            >
              {caseData.ticket_id}
            </a>
          ) : (
            "—"
          )}
        </td>
      )}
      <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
        {analysis.order_date ?? "—"}
      </td>
      <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
        {analysisLabel(analysis.analysis_type)}
      </td>
      <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
        {platformLabel(analysis.sequencing_platform)}
      </td>
      <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
        {sampleCount} sample{sampleCount !== 1 ? "s" : ""}
        {controlCount > 0 && <span className="text-gray-300 ml-1">+{controlCount} ctrl</span>}
      </td>
      <td className="px-4 py-3 text-xs text-gray-400">
        {/* Notes belong to the case, so every run of it shows the same count. */}
        {noteCount > 0 ? <span className="text-amber-600 font-medium">{noteCount}</span> : "—"}
      </td>
      <td className="px-4 py-3">
        {/* Status is the run's own: a reviewed run stays "Reviewed" once superseded. */}
        <Badge type={analysis.review?.reviewed ? "reviewed" : "pending"} />
      </td>
      <td className="px-4 py-3 text-xs text-gray-400">{analysis.review?.reviewed_by ?? "—"}</td>
      {showDelete && (
        <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={onDelete}
            className="text-xs text-gray-300 hover:text-red-500 transition-colors"
          >
            Delete
          </button>
        </td>
      )}
    </tr>
  );
}
