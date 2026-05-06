import type { Case, CaseNote, PathogenItem, Sample } from "../../../api/types";
import SignalPill, { type SignalKind } from "../../SignalPill";
import { TONE } from "../../palette";
import Badge from "../../Badge";
import KnownPathogensPanel from "../../KnownPathogensPanel";

interface CaseOverviewProps {
  caseData: Case;
  samples: Sample[];
  notes: CaseNote[];
  signals: SignalKind[];
  pathogenMap: Record<number, PathogenItem>;
  onJumpToSamples: () => void;
  onJumpToComments: () => void;
  onSelectSample: (sampleId: string) => void;
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

interface PipelineConfig {
  pipeline_name?: string;
  pipeline_version?: string;
}

interface PipelineInfo {
  pipeline_configuration?: PipelineConfig;
}

function pipelineLabel(c: Case): string {
  const info = c.pipeline_info as PipelineInfo | undefined;
  const cfg = info?.pipeline_configuration;
  if (!cfg?.pipeline_name) return "—";
  return cfg.pipeline_version ? `${cfg.pipeline_name} ${cfg.pipeline_version}` : cfg.pipeline_name;
}

export default function CaseOverview({
  caseData,
  samples,
  notes,
  signals,
  pathogenMap,
  onJumpToSamples,
  onJumpToComments,
  onSelectSample,
}: Readonly<CaseOverviewProps>) {
  const reviewed = (caseData.review as { reviewed?: boolean } | undefined)?.reviewed ?? false;
  const hasPathogen = signals.includes("pathogen");
  const orderDate = caseData.order_date as string | undefined;
  const sampleCount =
    (caseData.sample_count as number | undefined) ??
    samples.filter((s) => s.sample_type === "sample").length;
  const controlCount =
    (caseData.control_count as number | undefined) ??
    samples.filter((s) => s.sample_type === "negative_ctrl" || s.sample_type === "positive_ctrl")
      .length;
  const analysis = caseData.analysis_type as string | undefined;
  const platform = caseData.sequencing_platform as string | undefined;
  const ticket = caseData.ticket_id as string | undefined;

  const pathogenSample = hasPathogen
    ? samples.find(
        (s) => Array.isArray(s.all_taxon_ids) && (s.all_taxon_ids as number[]).length > 0
      )
    : null;

  const samplePreview = samples.slice(0, 4);
  const noteSlice = notes.slice(-2).reverse();
  const samplesLabel = controlCount
    ? `${sampleCount} (+${controlCount} ctrl)`
    : String(sampleCount);

  const meta: Array<[string, string]> = [
    ["Order date", relDay(orderDate)],
    [
      "Reviewer",
      reviewed
        ? String((caseData.review as { reviewed_by?: string } | undefined)?.reviewed_by ?? "—")
        : "—",
    ],
    ["Ticket", ticket ?? "—"],
    ["Status", reviewed ? "Reviewed" : "Pending"],
    ["Samples", samplesLabel],
    ["Analysis", analysis ?? "—"],
    ["Platform", platform ?? "—"],
    ["Pipeline", pipelineLabel(caseData)],
  ];

  return (
    <div className="flex flex-col gap-4">
      {hasPathogen && (
        <div
          className={`${TONE.danger.bg} ${TONE.danger.border} border border-l-[3px] rounded-lg px-4 py-3 flex items-center gap-3`}
          style={{ borderLeftColor: "rgb(220 38 38)" }}
        >
          <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="5" stroke="rgb(185 28 28)" strokeWidth="1.5" />
            <circle cx="8" cy="8" r="1.8" fill="rgb(185 28 28)" />
          </svg>
          <div className="flex-1">
            <div className={`text-sm font-semibold ${TONE.danger.fg}`}>
              Pathogen detected — requires review
            </div>
            {pathogenSample && (
              <div className={`text-xs ${TONE.danger.fg} opacity-90`}>
                in <span className="font-mono">{pathogenSample.sample_id}</span>
              </div>
            )}
          </div>
          <button
            onClick={onJumpToSamples}
            className={`${TONE.danger.fg} bg-white border ${TONE.danger.border} px-3 py-1.5 rounded-md text-xs hover:bg-red-50 transition-colors`}
          >
            View samples →
          </button>
        </div>
      )}

      <section className="bg-white border border-gray-100 rounded-lg p-5">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900 mb-3">
          Case summary
        </h3>
        <div className="grid grid-cols-4 gap-x-6 gap-y-3">
          {meta.map(([k, v]) => (
            <div key={k}>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">
                {k}
              </div>
              <div className="text-[12.5px] text-gray-900 font-medium mt-0.5 truncate" title={v}>
                {v}
              </div>
            </div>
          ))}
        </div>
        {signals.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-gray-100">
            {signals.map((s) => (
              <SignalPill key={s} kind={s} />
            ))}
          </div>
        )}
      </section>

      <section className="bg-white border border-gray-100 rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center">
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900 m-0">
            Samples
          </h3>
          <button
            onClick={onJumpToSamples}
            className="ml-auto text-[11px] text-blue-600 hover:underline"
          >
            See all {samples.length} →
          </button>
        </div>
        {samplePreview.length === 0 ? (
          <div className="px-4 py-6 text-center text-xs text-gray-400">
            No samples in this case.
          </div>
        ) : (
          samplePreview.map((s) => (
            <button
              key={s._id as string}
              onClick={() => onSelectSample(s._id as string)}
              className="grid items-center px-4 py-2.5 border-b border-gray-50 hover:bg-gray-50 transition-colors text-left w-full"
              style={{ gridTemplateColumns: "1fr auto auto auto" }}
            >
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-medium text-gray-900">{s.sample_id}</span>
                <Badge type={(s.sample_type as string | undefined) ?? "sample"} />
              </div>
              <span className="text-[11px] text-gray-500 mr-3">
                {(s.material as string | undefined) ?? "—"}
              </span>
              <span className="text-[11px] text-gray-500 mr-3">
                {(s.sample_source as string | undefined) ?? "—"}
              </span>
              <svg className="w-3 h-3 text-gray-300" viewBox="0 0 12 12" fill="none">
                <path
                  d="M4 3l3 3-3 3"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          ))
        )}
      </section>

      <section className="bg-white border border-gray-100 rounded-lg p-5">
        <div className="flex items-baseline mb-3">
          <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900 m-0">
            Recent comments
          </h3>
          <button
            onClick={onJumpToComments}
            className="ml-auto text-[11px] text-blue-600 hover:underline"
          >
            All comments →
          </button>
        </div>
        {noteSlice.length === 0 ? (
          <p className="text-xs text-gray-400">No comments yet.</p>
        ) : (
          noteSlice.map((n, i) => (
            <div
              key={n.id}
              className={`pb-3 ${i < noteSlice.length - 1 ? "mb-3 border-b border-gray-50" : ""}`}
            >
              <div className="flex gap-2 text-[11px] mb-1">
                <span className="font-semibold text-gray-800">{n.author}</span>
                <span className="text-gray-400 font-mono">
                  {n.created_at
                    ? new Date(n.created_at).toLocaleDateString("sv-SE", {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : ""}
                </span>
              </div>
              <p className="text-xs text-gray-600 leading-relaxed m-0 whitespace-pre-wrap">
                {n.text}
              </p>
            </div>
          ))
        )}
      </section>

      <KnownPathogensPanel samples={samples} pathogenMap={pathogenMap} />
    </div>
  );
}
