import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import type { Sample } from "../../../api/types";
import { getCaseKronaUrl } from "../../../api/cases";
import { getKronaUrl } from "../../../api/samples";
import { fmt, fmtPct } from "../../../utils/format";

export interface Classifier {
  name: string;
  db?: string;
  krona_id?: string;
}

interface TopTaxon {
  name: string;
  superkingdom?: string;
  pct?: number;
  abundance?: number;
}

interface CaseClassifiersProps {
  caseId: string;
  classifiers: Classifier[];
  samples: Sample[];
  showKrona: boolean;
}

interface SampleClassifierQc {
  pct_unclassified?: number;
  num_species?: number;
  num_genera?: number;
}

interface TaxprofilerInfo {
  classifiers?: Record<string, SampleClassifierQc>;
}

interface TranaInfo {
  nanoplot_unprocessed?: { number_of_reads?: number };
}

function superkingdomColor(kingdom: string | undefined): string {
  const COLORS: Record<string, string> = {
    Bacteria: "bg-blue-400",
    Viruses: "bg-red-400",
    Eukaryota: "bg-amber-400",
    Archaea: "bg-purple-400",
  };
  return COLORS[kingdom ?? ""] ?? "bg-gray-300";
}

// Renders the classifier results table and (optionally) the Krona iframe for the
// case's samples. Extracted from the legacy CaseDetail page to fit the case-view
// sidebar's "Krona viewer" section. Behaviour kept identical to legacy.
export default function CaseClassifiers({
  caseId,
  classifiers,
  samples,
  showKrona,
}: Readonly<CaseClassifiersProps>) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const isTrana = samples.some((s) => s.trana);

  const [tab, setTab] = useState<string | null>(
    searchParams.get("classifier") ?? classifiers[0]?.name ?? null
  );
  const [kronaUrls, setKronaUrls] = useState<Record<string, string>>({});
  const [kronaErrors, setKronaErrors] = useState<Record<string, boolean>>({});
  const [kronaSelectedSample, setKronaSelectedSample] = useState<string | null>(null);

  useEffect(() => {
    if (!classifiers.length) return;
    const requested = searchParams.get("classifier");
    const match = classifiers.find((c) => c.name === requested);
    if (match) setTab(requested);
    else setTab((prev) => prev ?? classifiers[0].name);
  }, [classifiers, searchParams]);

  useEffect(() => {
    if (!showKrona) return;

    if (isTrana) {
      const kronaSamples = samples.filter((s) => s.has_krona);
      setKronaSelectedSample((prev) => prev ?? (kronaSamples[0]?._id as string) ?? null);
      let cancelled = false;
      Promise.all(
        kronaSamples.map(async (s) => {
          try {
            const url = await getKronaUrl(s._id as string);
            return { id: s._id as string, url, error: false };
          } catch {
            return { id: s._id as string, url: null, error: true };
          }
        })
      ).then((entries) => {
        if (cancelled) return;
        const urls: Record<string, string> = {};
        const errors: Record<string, boolean> = {};
        entries.forEach(({ id, url, error }) => {
          if (error) errors[id] = true;
          else if (url) urls[id] = url;
        });
        setKronaUrls(urls);
        setKronaErrors(errors);
      });
      return () => {
        cancelled = true;
      };
    }

    let cancelled = false;
    Promise.all(
      classifiers
        .filter((clf) => clf.krona_id)
        .map(async (clf) => {
          try {
            const url = await getCaseKronaUrl(caseId, clf.name);
            return { name: clf.name, url, error: false };
          } catch {
            return { name: clf.name, url: null, error: true };
          }
        })
    ).then((entries) => {
      if (cancelled) return;
      const urls: Record<string, string> = {};
      const errors: Record<string, boolean> = {};
      entries.forEach(({ name, url, error }) => {
        if (error) errors[name] = true;
        else if (url) urls[name] = url;
      });
      setKronaUrls(urls);
      setKronaErrors(errors);
    });
    return () => {
      cancelled = true;
    };
  }, [classifiers, samples, caseId, isTrana, showKrona]);

  useEffect(() => {
    return () => {
      Object.values(kronaUrls).forEach(URL.revokeObjectURL);
    };
  }, [kronaUrls]);

  if (!classifiers.length) {
    return (
      <section className="bg-white border border-gray-100 rounded-lg p-8 text-center text-sm text-gray-400">
        No classifier results available for this case.
      </section>
    );
  }

  const activeClassifier = classifiers.find((c) => c.name === tab) ?? classifiers[0];
  const kronaIsLoading = !kronaUrls[activeClassifier.name] && !kronaErrors[activeClassifier.name];

  return (
    <section className="bg-white border border-gray-100 rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-gray-900 m-0">
          Classifier results
        </h3>
        <div className="ml-auto flex gap-1.5">
          {classifiers.map((clf) => (
            <button
              key={clf.name}
              onClick={() => {
                setTab(clf.name);
                setSearchParams({ classifier: clf.name });
              }}
              className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                tab === clf.name
                  ? "bg-gray-900 text-white font-medium"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              }`}
            >
              {clf.name}
            </button>
          ))}
        </div>
      </div>

      <div className="px-4 pt-3 pb-1">
        <p className="text-xs text-gray-300 font-mono">{activeClassifier.db}</p>
      </div>

      <table className="w-full text-left border-collapse">
        <thead>
          <tr>
            {(isTrana
              ? ["Sample", "Reads (raw)", "Top taxa"]
              : [
                  "Sample",
                  "Unclassified",
                  "Host",
                  "Species",
                  "Genera",
                  "Positive control",
                  "Top taxa",
                ]
            ).map((h) => (
              <th
                key={h}
                className="px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-gray-400 border-b border-gray-100 whitespace-nowrap"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {samples.map((s) => {
            const topTaxaMap = s.top_taxa as Record<string, TopTaxon[]> | undefined;
            const topTaxa: TopTaxon[] = topTaxaMap?.[activeClassifier.name] ?? [];
            const trana = s.trana as TranaInfo | undefined;
            const tp = s.taxprofiler as TaxprofilerInfo | undefined;
            const hostPct = s.host_pct as Record<string, number> | undefined;
            const spikeInMap = s.spike_in_taxa as Record<string, TopTaxon[]> | undefined;

            const topTaxaCell = (
              <td className="px-4 py-1.5">
                <div className="flex flex-col gap-0">
                  {topTaxa.map((t) => (
                    <span
                      key={t.name}
                      className="flex items-center gap-1"
                      style={{ fontSize: "11px", lineHeight: "1.4" }}
                    >
                      <span
                        className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${superkingdomColor(t.superkingdom)}`}
                      />
                      <span className="text-gray-600 italic truncate max-w-36">{t.name}</span>
                      {t.pct != null && (
                        <span className="text-gray-400 flex-shrink-0">{t.pct.toFixed(1)}%</span>
                      )}
                    </span>
                  ))}
                </div>
              </td>
            );

            return (
              <tr
                key={s._id as string}
                onClick={() => navigate(`/samples/${s._id}?classifier=${activeClassifier.name}`)}
                className="cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors"
              >
                <td className="px-4 py-1.5 font-mono text-xs text-gray-700">
                  {s.sample_id ?? "—"}
                </td>
                {isTrana ? (
                  <>
                    <td className="px-4 py-1.5 text-xs text-gray-700">
                      {fmt(trana?.nanoplot_unprocessed?.number_of_reads)}
                    </td>
                    {topTaxaCell}
                  </>
                ) : (
                  (() => {
                    const clfQc = tp?.classifiers?.[activeClassifier.name];
                    const spikeIn: TopTaxon[] = spikeInMap?.[activeClassifier.name] ?? [];
                    return (
                      <>
                        <td className="px-4 py-1.5 text-xs text-gray-700">
                          {fmtPct(clfQc?.pct_unclassified)}
                        </td>
                        <td className="px-4 py-1.5 text-xs text-gray-700">
                          {hostPct?.[activeClassifier.name] != null
                            ? `${hostPct[activeClassifier.name]}%`
                            : "—"}
                        </td>
                        <td className="px-4 py-1.5 text-xs text-gray-700">
                          {fmt(clfQc?.num_species)}
                        </td>
                        <td className="px-4 py-1.5 text-xs text-gray-700">
                          {fmt(clfQc?.num_genera)}
                        </td>
                        <td className="px-4 py-1.5 text-xs">
                          {spikeIn.length > 0 ? (
                            <div className="flex flex-col gap-0.5">
                              {spikeIn.map((t) => (
                                <span key={t.name} className="text-gray-600 italic">
                                  {t.name}
                                  {t.pct != null && (
                                    <span className="not-italic text-gray-400 ml-1">
                                      {t.pct}% ({t.abundance?.toLocaleString()})
                                    </span>
                                  )}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-gray-300">Not detected</span>
                          )}
                        </td>
                        {topTaxaCell}
                      </>
                    );
                  })()
                )}
              </tr>
            );
          })}
        </tbody>
      </table>

      {showKrona && (
        <div className="p-4 border-t border-gray-50">
          {isTrana
            ? kronaSelectedSample && (
                <>
                  <div className="flex gap-1.5 mb-3">
                    {samples
                      .filter((s) => s.has_krona)
                      .map((s) => (
                        <button
                          key={s._id as string}
                          onClick={() => setKronaSelectedSample(s._id as string)}
                          className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                            kronaSelectedSample === s._id
                              ? "bg-gray-900 text-white font-medium"
                              : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                          }`}
                        >
                          {s.sample_id}
                        </button>
                      ))}
                  </div>
                  {kronaErrors[kronaSelectedSample] && (
                    <p className="text-xs text-red-400">Krona file could not be loaded.</p>
                  )}
                  {kronaUrls[kronaSelectedSample] && (
                    <iframe
                      key={kronaUrls[kronaSelectedSample]}
                      src={kronaUrls[kronaSelectedSample]}
                      title={`Krona — ${samples.find((s) => s._id === kronaSelectedSample)?.sample_id}`}
                      className="w-full rounded-lg border border-gray-100"
                      style={{ height: "75vh" }}
                      sandbox="allow-scripts allow-popups allow-forms"
                    />
                  )}
                </>
              )
            : activeClassifier.krona_id && (
                <>
                  {kronaErrors[activeClassifier.name] && (
                    <p className="text-xs text-red-400">Krona file could not be loaded.</p>
                  )}
                  {kronaIsLoading && (
                    <div className="flex items-center justify-center h-40 text-sm text-gray-400">
                      Loading Krona…
                    </div>
                  )}
                  {kronaUrls[activeClassifier.name] && (
                    <iframe
                      key={kronaUrls[activeClassifier.name]}
                      src={kronaUrls[activeClassifier.name]}
                      title={`Krona — ${activeClassifier.name}`}
                      className="w-full rounded-lg border border-gray-100"
                      style={{ height: "75vh" }}
                      sandbox="allow-scripts allow-popups allow-forms"
                    />
                  )}
                </>
              )}
        </div>
      )}
    </section>
  );
}
