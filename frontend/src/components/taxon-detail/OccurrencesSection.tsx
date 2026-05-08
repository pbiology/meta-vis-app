import React, { useState } from "react";
import { useTaxonOccurrences } from "../../hooks/queries/useTaxa";
import { fmt } from "../../utils/format";
import type { OccurrencesData } from "./types";

const WINDOWS = [30, 90, 180, 365];

interface OccurrencesSectionProps {
  taxonId: number;
}

export default function OccurrencesSection({ taxonId }: Readonly<OccurrencesSectionProps>) {
  const [windowDays, setWindowDays] = useState(90);
  const { data, isLoading } = useTaxonOccurrences(taxonId, windowDays);
  const occ = data as unknown as OccurrencesData | undefined;

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">
          Occurrences
        </p>
        <div className="flex gap-1">
          {WINDOWS.map((w) => (
            <button
              key={w}
              onClick={() => setWindowDays(w)}
              className={`text-xs px-2.5 py-1 rounded-full transition-colors ${
                windowDays === w
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              }`}
            >
              {w}d
            </button>
          ))}
        </div>
      </div>

      {isLoading && <div className="px-4 py-8 text-xs text-gray-400 text-center">Loading…</div>}
      {!isLoading && (!occ || occ.total_cases === 0) && (
        <div className="px-4 py-8 text-xs text-gray-300 text-center">
          Not detected in any case in the last {windowDays} days.
        </div>
      )}
      {!isLoading && occ && occ.total_cases > 0 && (
        <>
          <div className="px-4 py-2.5 border-b border-gray-50 flex items-center gap-2">
            <span className="text-xs text-gray-400">
              Detected in <span className="font-medium text-gray-700">{occ.total_cases}</span>{" "}
              {occ.total_cases === 1 ? "case" : "cases"} in the last {windowDays} days
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr>
                  {["Case", "Order date", "Samples", "Reads by sample × classifier"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-2 text-xs font-medium text-gray-400 border-b border-gray-100"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {occ.cases.map((c) => {
                  const classifiers = occ.all_classifiers ?? c.classifiers ?? [];
                  const gridCols = `minmax(0, auto) repeat(${classifiers.length}, minmax(0, 1fr))`;
                  return (
                    <tr
                      key={c.case_id}
                      className="border-t border-gray-50 hover:bg-gray-50 align-top"
                    >
                      <td className="px-4 py-2.5">
                        <a
                          href={`/case/${c.case_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs font-mono text-blue-600 hover:underline"
                        >
                          {c.case_id}
                        </a>
                      </td>
                      <td className="px-4 py-2.5 text-xs text-gray-500 tabular-nums">
                        {c.order_date ?? "—"}
                      </td>
                      <td className="px-4 py-2.5 text-xs text-gray-500 tabular-nums">
                        {c.sample_count}
                      </td>
                      <td className="px-4 py-2.5">
                        {classifiers.length === 0 ? (
                          <span className="text-xs text-gray-300">—</span>
                        ) : (
                          <div
                            className="inline-grid gap-x-4 gap-y-1 items-baseline"
                            style={{ gridTemplateColumns: gridCols }}
                          >
                            <span />
                            {classifiers.map((cl) => (
                              <span
                                key={cl}
                                className="text-[10px] uppercase tracking-wider text-gray-400 text-right"
                              >
                                {cl}
                              </span>
                            ))}
                            {c.samples.map((s) => (
                              <React.Fragment key={s.sample_id}>
                                <span
                                  className="text-xs font-mono text-gray-500 truncate max-w-[12rem]"
                                  title={s.sample_id}
                                >
                                  {s.sample_id}
                                </span>
                                {classifiers.map((cl) => {
                                  const v = s.reads?.[cl];
                                  return (
                                    <span
                                      key={cl}
                                      className={`text-xs tabular-nums text-right ${
                                        v == null ? "text-gray-300" : "text-gray-700"
                                      }`}
                                    >
                                      {v == null ? "—" : fmt(v)}
                                    </span>
                                  );
                                })}
                              </React.Fragment>
                            ))}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
