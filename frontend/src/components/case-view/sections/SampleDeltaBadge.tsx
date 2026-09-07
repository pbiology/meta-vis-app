import type { SampleReadDelta } from "../../../api/types";
import { fmt } from "../../../utils/format";

/**
 * Marks how a sample's raw read count compares to an earlier run of its case.
 *
 * Cases are delivered partially first, then topped up for any sample short of
 * the agreed data amount, so "this one never got its top-up" is as important
 * to show as "this one did" — every comparable row is labelled rather than
 * leaving the reader to infer meaning from a blank cell. Renders nothing at
 * all when there is no earlier run to compare against.
 */

const compact = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 1,
});

const STYLES: Record<SampleReadDelta["status"], string> = {
  increased: "bg-green-50 text-green-700",
  decreased: "bg-amber-50 text-amber-700",
  unchanged: "bg-gray-50 text-gray-400",
  new: "bg-blue-50 text-blue-600",
  unknown: "bg-gray-50 text-gray-400",
};

function label(delta: SampleReadDelta): string {
  switch (delta.status) {
    case "increased":
      return `▲ +${compact.format(delta.delta_reads ?? 0)}`;
    case "decreased":
      return `▼ −${compact.format(Math.abs(delta.delta_reads ?? 0))}`;
    case "unchanged":
      return "no top-up";
    case "new":
      return "new";
    case "unknown":
      return "?";
  }
}

function pctSuffix(pct: number | null): string {
  if (pct === null) return "";
  const sign = pct > 0 ? "+" : "";
  return ` (${sign}${pct}%)`;
}

function tooltip(delta: SampleReadDelta): string {
  if (delta.status === "new") {
    return "Not present in any earlier run of this case.";
  }
  const from = `v${delta.previous_version}: ${fmt(delta.previous_reads)}`;
  if (delta.status === "unknown") {
    return `Read count missing — cannot compare with ${from}.`;
  }
  const change = pctSuffix(delta.pct_change);
  const to = `this run: ${fmt(delta.current_reads)}`;
  return delta.status === "unchanged"
    ? `Unchanged since ${from} — this sample gained no data.`
    : `${from} → ${to}${change}`;
}

/**
 * Fixed footprint, kept even when there is no badge to show.
 *
 * The samples table uses automatic layout, so content decides column widths:
 * without a reserved slot, a re-sequenced case's table and a first-run case's
 * table size their columns differently and stop lining up when you move
 * between cases. Wide enough for the longest label ("no top-up") and the
 * largest plausible delta ("▲ +999.9M"); anything longer merely widens the
 * column, as it did before.
 */
const SLOT = "inline-flex shrink-0 w-[4.75rem]";

interface SampleDeltaBadgeProps {
  delta?: SampleReadDelta;
}

export default function SampleDeltaBadge({ delta }: Readonly<SampleDeltaBadgeProps>) {
  if (!delta) return <span className={SLOT} aria-hidden="true" />;
  return (
    <span className={SLOT}>
      <span
        title={tooltip(delta)}
        className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium whitespace-nowrap ${STYLES[delta.status]}`}
      >
        {label(delta)}
      </span>
    </span>
  );
}
