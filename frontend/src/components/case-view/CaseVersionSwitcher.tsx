import { useState } from "react";
import type { AnalysisSummary } from "../../api/types";

interface CaseVersionSwitcherProps {
  caseId: string;
  analyses: AnalysisSummary[];
  currentVersion: number;
}

/**
 * "v2 of 3" pill listing every analysis of the case.
 *
 * There is no comparison view by design — runs are read side by side — so each
 * entry opens in a new tab rather than navigating away from the current one.
 */
export default function CaseVersionSwitcher({
  caseId,
  analyses,
  currentVersion,
}: Readonly<CaseVersionSwitcherProps>) {
  const [open, setOpen] = useState(false);

  // A case with a single run has nothing to switch between.
  if (analyses.length < 2) return null;

  function hrefFor(a: AnalysisSummary): string {
    return a.is_latest ? `/cases/${caseId}` : `/cases/${caseId}/analyses/${a.version}`;
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-1 text-[11px] font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-md px-2 py-1 transition-colors"
      >
        v{currentVersion} of {analyses.length}
        <svg
          className={`w-2.5 h-2.5 transition-transform ${open ? "rotate-180" : ""}`}
          viewBox="0 0 16 16"
          fill="none"
        >
          <path
            d="M4 6l4 4 4-4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {open && (
        <>
          <button
            className="fixed inset-0 z-10 cursor-default"
            aria-label="Close version list"
            onClick={() => setOpen(false)}
          />
          <div
            role="menu"
            className="absolute left-0 top-full mt-1 z-20 w-56 bg-white border border-gray-100 rounded-lg shadow-lg py-1"
          >
            {analyses.map((a) => (
              <a
                key={a.version}
                href={hrefFor(a)}
                target="_blank"
                rel="noopener noreferrer"
                role="menuitem"
                onClick={() => setOpen(false)}
                className={`flex items-center gap-2 px-3 py-1.5 text-[11px] no-underline hover:bg-gray-50 ${
                  a.version === currentVersion ? "text-gray-900 font-medium" : "text-gray-600"
                }`}
              >
                <span className="font-mono">v{a.version}</span>
                {a.is_latest && (
                  <span className="px-1 py-0.5 rounded text-[10px] bg-blue-50 text-blue-600">
                    latest
                  </span>
                )}
                <span className="text-gray-400 ml-auto">{a.order_date ?? "—"}</span>
                <span className={a.review?.reviewed ? "text-green-600" : "text-amber-500"}>
                  {a.review?.reviewed ? "reviewed" : "pending"}
                </span>
              </a>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
