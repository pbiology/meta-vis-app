import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useCases, useCaseStats, usePathogenCases } from "../hooks/queries/useCases";
import { useOutbreaks } from "../hooks/queries/useAlerts";
import { useNtcContaminantCaseIds } from "../hooks/queries/useNtc";
import StatCard from "../components/dashboard/StatCard";
import VolumeChart from "../components/dashboard/VolumeChart";
import CaseRow from "../components/dashboard/CaseRow";
import TopPathogensPanel from "../components/dashboard/TopPathogensPanel";
import ReviewerActivityPanel from "../components/dashboard/ReviewerActivityPanel";
import { VOLUME_14D, MOCK_AVG_TURNAROUND } from "../components/dashboard/mockData";
import type { SignalKind } from "../components/SignalPill";

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function todayLabel(): string {
  return new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export default function Dashboard() {
  const statsQ = useCaseStats();
  const casesQ = useCases({ page: 1 });
  const outbreaksQ = useOutbreaks(14);
  const pathogenCasesQ = usePathogenCases();
  const ntcCaseIdsQ = useNtcContaminantCaseIds();

  const stats = statsQ.data ?? { total: 0, pending: 0, reviewed: 0 };
  const recent = useMemo(() => casesQ.data?.items?.slice(0, 6) ?? [], [casesQ.data]);
  const outbreakIds = useMemo(
    () => new Set(outbreaksQ.data?.outbreaks.flatMap((o) => o.case_ids) ?? []),
    [outbreaksQ.data]
  );
  const pathogenIds = useMemo(
    () => new Set(pathogenCasesQ.data?.case_ids ?? []),
    [pathogenCasesQ.data]
  );
  const ntcIds = useMemo(() => new Set(ntcCaseIdsQ.data?.case_ids ?? []), [ntcCaseIdsQ.data]);

  const signalsFor = useMemo(() => {
    return (caseId: string): SignalKind[] => {
      const out: SignalKind[] = [];
      if (pathogenIds.has(caseId)) out.push("pathogen");
      if (outbreakIds.has(caseId)) out.push("outbreak");
      if (ntcIds.has(caseId)) out.push("ntc");
      return out;
    };
  }, [outbreakIds, pathogenIds, ntcIds]);

  const hasError =
    statsQ.isError ||
    casesQ.isError ||
    outbreaksQ.isError ||
    pathogenCasesQ.isError ||
    ntcCaseIdsQ.isError;

  const pending = (stats.pending as number | undefined) ?? 0;
  const pathogenFlags = pathogenIds.size;
  const sevenDayCutoff = isoDaysAgo(7);
  const casesThisWeek = recent.filter((c) => (c.order_date ?? "") >= sevenDayCutoff).length;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-6 pt-5 pb-4 bg-white border-b border-gray-100 flex items-end gap-4 flex-shrink-0">
        <div className="flex-1">
          <h1 className="text-xl font-semibold text-gray-900 tracking-tight m-0">Dashboard</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            {todayLabel()} · all clinical metagenomics activity
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            to="/cases"
            className="px-3 py-1.5 text-xs rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 transition-colors no-underline"
          >
            All cases →
          </Link>
        </div>
      </header>

      {hasError && (
        <div className="px-6 py-2 bg-amber-50 border-b border-amber-200 text-xs text-amber-700 flex-shrink-0">
          Some dashboard data failed to load — counts and signals may be incomplete.
        </div>
      )}

      <div
        className="flex-1 overflow-y-auto p-5 grid gap-3"
        style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gridAutoRows: "min-content" }}
      >
        {/* Top row — 4 stat cards */}
        <StatCard
          label="Pending review"
          value={pending}
          sub={pending === 0 ? "All clear" : `${pending} awaiting review`}
          tone="warn"
          accent
        />
        <StatCard
          label="Pathogen flags"
          value={pathogenFlags}
          sub="across all open cases"
          tone="danger"
          accent
        />
        <StatCard
          label="Cases this week"
          value={casesThisWeek}
          sub="last 7 days · from recent fetch"
        />
        <StatCard
          label="Avg turnaround"
          value={MOCK_AVG_TURNAROUND}
          sub="target ≤ 3 days · demo"
          tone="ok"
          accent
        />

        {/* Volume chart spanning 3 cols */}
        <section
          className="bg-white border border-gray-100 rounded-lg p-4"
          style={{ gridColumn: "span 3" }}
        >
          <div className="flex items-baseline gap-3 mb-3">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900 m-0">
              Case volume
            </h3>
            <span className="text-[11px] text-gray-400">last 14 days</span>
            <span
              className="text-[10px] text-amber-700 font-medium"
              title="Backed by mock data — TODO(backend)"
            >
              demo
            </span>
            <div className="ml-auto flex gap-3.5 text-[11px]">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 bg-gray-200 rounded-sm" />
                <span>Routine</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 bg-red-600 rounded-sm" />
                <span>With pathogen</span>
              </span>
            </div>
          </div>
          <VolumeChart data={VOLUME_14D} height={110} />
          <div className="flex justify-between mt-2 text-[10px] text-gray-400 font-mono">
            <span>14d ago</span>
            <span>Today</span>
          </div>
        </section>

        {/* Top pathogens — 1 col */}
        <TopPathogensPanel />

        {/* Recent cases — 3 cols */}
        <section
          className="bg-white border border-gray-100 rounded-lg overflow-hidden flex flex-col"
          style={{ gridColumn: "span 3" }}
        >
          <div className="px-4 py-3 flex items-center">
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900 m-0">
              Recent cases
            </h3>
            <Link
              to="/cases"
              className="ml-auto text-[11px] text-blue-600 hover:underline no-underline"
            >
              View all →
            </Link>
          </div>
          {recent.length === 0 ? (
            <div className="px-4 py-8 text-center text-xs text-gray-400">No cases yet.</div>
          ) : (
            recent.map((c) => <CaseRow key={c.case_id} c={c} signals={signalsFor(c.case_id)} />)
          )}
        </section>

        {/* Reviewer leaderboard */}
        <ReviewerActivityPanel />
      </div>
    </div>
  );
}
