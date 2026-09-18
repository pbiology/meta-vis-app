import { useState } from "react";
import { fmt, fmtPct } from "../../utils/format";
import type { CladeColumn, CladeUnit, UnplacedTaxon } from "../../api/types";

const REASON_LABEL: Record<UnplacedTaxon["reason"], string> = {
  deleted: "deleted by NCBI",
  not_in_taxonomy: "not in taxonomy reference",
};

interface CladeUnplacedNoticeProps {
  unplaced: UnplacedTaxon[];
  columns: CladeColumn[];
  unit: CladeUnit;
}

/**
 * Signal in this analysis that could not be placed in the taxonomy. Shown for
 * the whole run, not just this clade: without a lineage there is no telling
 * whether it belongs here, so it must never be hidden.
 */
export default function CladeUnplacedNotice({
  unplaced,
  columns,
  unit,
}: Readonly<CladeUnplacedNoticeProps>) {
  const [open, setOpen] = useState(false);
  if (unplaced.length === 0) return null;

  return (
    <div className="mx-4 my-3 px-3 py-2.5 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="text-left w-full"
      >
        {unplaced.length} {unplaced.length === 1 ? "taxon" : "taxa"} in this run could not be placed
        in the taxonomy and may belong to this group.{" "}
        <span className="underline">{open ? "Hide" : "Show"}</span>
      </button>
      {open && (
        <table className="w-full mt-2 text-left">
          <thead>
            <tr>
              <th className="py-1 pr-3 font-medium">Taxon</th>
              <th className="py-1 pr-3 font-medium">Reason</th>
              {columns.map((col) => (
                <th key={col.sample_id} className="py-1 pl-3 font-medium font-mono text-right">
                  {col.sample_id}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {unplaced.map((u) => (
              <tr key={u.taxon_id} className="border-t border-amber-100 align-top">
                <td className="py-1 pr-3">
                  <span className="italic">{u.name ?? "unnamed"}</span>{" "}
                  <span className="text-amber-600">· {u.taxon_id}</span>
                  {u.merged_from.length > 0 && (
                    <div className="text-[10px] text-amber-600">
                      includes retired taxid {u.merged_from.join(", ")}
                    </div>
                  )}
                </td>
                <td className="py-1 pr-3">{REASON_LABEL[u.reason]}</td>
                {columns.map((col) => {
                  const cell = u.cells[col.sample_id];
                  return (
                    <td key={col.sample_id} className="py-1 pl-3 text-right tabular-nums">
                      {cell ? formatDirect(cell.direct, unit) : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function formatDirect(value: number, unit: CladeUnit): string {
  return unit === "fraction" ? fmtPct(value * 100, 2) : fmt(value);
}
