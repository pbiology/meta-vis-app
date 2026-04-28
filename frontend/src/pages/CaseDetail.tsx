import { useState, useEffect, useMemo } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import {
  getCase,
  getCaseSamples,
  reviewCase,
  unreviewCase,
  getCaseKronaUrl,
  getCaseMultiQCUrl,
  addNote,
  deleteNote,
} from "../api/cases";
import { getPathogens } from "../api/alerts";
import { getKronaUrl } from "../api/samples";
import Badge from "../components/Badge";
import { useAuth } from "../context/AuthContext";
import { fmt, fmtPct } from "../utils/format";
import { useRequiredParam } from "../utils/routeParams";
import type { Case, Sample, PathogenItem } from "../api/types";

const FILTERS = ["All", "Sample", "Controls"] as const;
type Filter = (typeof FILTERS)[number];

interface Classifier {
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

export default function CaseDetail() {
  const caseId = useRequiredParam("caseId");
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { role, user } = useAuth();

  const [caseData, setCaseData] = useState<Case | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [pathogenMap, setPathogenMap] = useState<Record<number, PathogenItem>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("All");
  const [reviewing, setReviewing] = useState(false);
  const [unreviewConfirm, setUnreviewConfirm] = useState(false);
  const [kronaUrls, setKronaUrls] = useState<Record<string, string>>({});
  const [kronaErrors, setKronaErrors] = useState<Record<string, boolean>>({});
  const [kronaSelectedSample, setKronaSelectedSample] = useState<string | null>(null);
  const [kronaTab, setKronaTab] = useState<string | null>(searchParams.get("classifier"));
  const [provenanceOpen, setProvenanceOpen] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [noteSaving, setNoteSaving] = useState(false);
  const [multiqcUrl, setMultiqcUrl] = useState<string | null>(null);
  const [multiqcLoading, setMultiqcLoading] = useState(false);
  const [multiqcError, setMultiqcError] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [fetchedCase, samplesData, pathogens] = await Promise.all([
          getCase(caseId),
          getCaseSamples(caseId),
          getPathogens(),
        ]);
        setCaseData(fetchedCase);
        setSamples(samplesData);
        setPathogenMap(Object.fromEntries(pathogens.map((p) => [p.taxon_id, p])));

        const classifiers = (fetchedCase.classifiers as Classifier[] | undefined) ?? [];
        if (fetchedCase.has_krona && classifiers.length) {
          const requestedClassifier = searchParams.get("classifier");
          const match = classifiers.find((c) => c.name === requestedClassifier);
          setKronaTab(match ? requestedClassifier : classifiers[0].name);

          const isTrana = samplesData.some((s) => s.trana);
          if (isTrana) {
            const kronasamples = samplesData.filter((s) => s.has_krona);
            setKronaSelectedSample((kronasamples[0]?._id as string | undefined) ?? null);
            const urlEntries = await Promise.all(
              kronasamples.map(async (s) => {
                try {
                  const url = await getKronaUrl(s._id as string);
                  return { id: s._id as string, url, error: false };
                } catch {
                  return { id: s._id as string, url: null, error: true };
                }
              })
            );
            const urls: Record<string, string> = {};
            const errors: Record<string, boolean> = {};
            urlEntries.forEach(({ id, url, error }) => {
              if (error) errors[id] = true;
              else if (url) urls[id] = url;
            });
            setKronaUrls(urls);
            setKronaErrors(errors);
          } else {
            const urlEntries = await Promise.all(
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
            );
            const urls: Record<string, string> = {};
            const errors: Record<string, boolean> = {};
            urlEntries.forEach(({ name, url, error }) => {
              if (error) errors[name] = true;
              else if (url) urls[name] = url;
            });
            setKronaUrls(urls);
            setKronaErrors(errors);
          }
        }
      } catch {
        setError("Failed to load case.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [caseId]);

  async function handleReview() {
    setReviewing(true);
    try {
      const result = (await reviewCase(caseId)) as Case & { reviewed_by?: string };
      setCaseData((prev) => {
        if (!prev) return prev;
        const prevReview = (prev.review as Record<string, unknown>) ?? {};
        return {
          ...prev,
          review: { ...prevReview, reviewed: true, reviewed_by: result.reviewed_by },
        } as Case;
      });
    } catch {
      alert("Failed to mark as reviewed.");
    } finally {
      setReviewing(false);
    }
  }

  async function handleUnreview() {
    setUnreviewConfirm(false);
    setReviewing(true);
    try {
      await unreviewCase(caseId);
      setCaseData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          review: { reviewed: false, reviewed_by: null, reviewed_at: null, notes: null },
        } as Case;
      });
    } catch {
      alert("Failed to remove review.");
    } finally {
      setReviewing(false);
    }
  }

  async function handleAddNote() {
    if (!noteText.trim()) return;
    setNoteSaving(true);
    try {
      const note = await addNote(caseId, noteText);
      setCaseData((prev) => {
        if (!prev) return prev;
        const prevNotes = (prev.notes as unknown[] | undefined) ?? [];
        return { ...prev, notes: [...prevNotes, note] } as Case;
      });
      setNoteText("");
    } catch {
      alert("Failed to save note.");
    } finally {
      setNoteSaving(false);
    }
  }

  async function handleDeleteNote(index: number) {
    try {
      await deleteNote(caseId, index);
      setCaseData((prev) => {
        if (!prev) return prev;
        const prevNotes = (prev.notes as unknown[] | undefined) ?? [];
        return { ...prev, notes: prevNotes.filter((_, i) => i !== index) } as Case;
      });
    } catch {
      alert("Failed to delete note.");
    }
  }

  async function loadMultiqc(): Promise<string | null> {
    if (multiqcUrl) return multiqcUrl;
    setMultiqcLoading(true);
    setMultiqcError(false);
    try {
      const url = await getCaseMultiQCUrl(caseId);
      setMultiqcUrl(url);
      return url;
    } catch {
      setMultiqcError(true);
      return null;
    } finally {
      setMultiqcLoading(false);
    }
  }

  async function handleOpenMultiqc() {
    const url = await loadMultiqc();
    if (url) window.open(url, "_blank");
  }

  async function handleDownloadMultiqc() {
    const url = await loadMultiqc();
    if (!url) return;
    const a = document.createElement("a");
    a.href = url;
    a.download = `multiqc_${caseId}.html`;
    a.click();
  }

  const filtered = useMemo(() => {
    if (filter === "Sample") return samples.filter((s) => s.sample_type === "sample");
    if (filter === "Controls")
      return samples.filter(
        (s) => s.sample_type === "negative_ctrl" || s.sample_type === "positive_ctrl"
      );
    return samples;
  }, [samples, filter]);

  const review = caseData?.review as { reviewed?: boolean; reviewed_by?: string } | undefined;
  const reviewed = review?.reviewed;
  const classifiers = (caseData?.classifiers as Classifier[] | undefined) ?? [];
  const notes =
    (caseData?.notes as { author?: string; text?: string; created_at?: string }[] | undefined) ??
    [];
  const ticketId = caseData?.ticket_id as string | undefined;
  const ticketUrl = caseData?.ticket_url as string | undefined;

  if (loading)
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">Loading…</div>
    );
  if (error)
    return (
      <div className="flex items-center justify-center h-full text-sm text-red-500">{error}</div>
    );

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <button
          onClick={() => navigate("/cases")}
          className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1 transition-colors"
        >
          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
            <path
              d="M10 3L5 8l5 5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Cases
        </button>
        <span className="text-gray-200">/</span>
        <h1 className="text-sm font-medium text-gray-900 font-mono flex-1 flex items-center gap-2">
          {caseId}
          {ticketId &&
            (ticketUrl ? (
              <a
                href={ticketUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-normal text-blue-600 hover:text-blue-800 hover:underline"
                title="Open Freshdesk ticket"
              >
                #{ticketId}
              </a>
            ) : (
              <span className="text-xs font-normal text-gray-400">#{ticketId}</span>
            ))}
        </h1>
        <Badge type={reviewed ? "reviewed" : "pending"} />
        <button
          onClick={() => setNotesOpen((o) => !o)}
          className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-colors ${
            notesOpen
              ? "border-amber-300 bg-amber-50 text-amber-700"
              : "border-gray-200 text-gray-500 hover:bg-gray-50"
          }`}
        >
          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
            <path
              d="M2 3h12v8H9l-3 2.5V11H2V3z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
          </svg>
          Notes
          {notes.length > 0 && (
            <span className="bg-amber-100 text-amber-700 text-xs px-1.5 py-0.5 rounded-full font-medium">
              {notes.length}
            </span>
          )}
        </button>
        {!reviewed && role !== "reader" && (
          <button
            onClick={handleReview}
            disabled={reviewing}
            className="btn-primary disabled:opacity-50"
          >
            {reviewing ? "Saving…" : "Mark case as reviewed"}
          </button>
        )}
        {reviewed && (
          <>
            <button
              onClick={() => setUnreviewConfirm(true)}
              className="text-xs text-green-600 hover:text-green-800 transition-colors"
            >
              ● Reviewed by {review?.reviewed_by}
            </button>
            {unreviewConfirm && (
              <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
                <div className="bg-white rounded-xl border border-gray-100 shadow-lg p-6 w-80 flex flex-col gap-4">
                  <p className="text-sm font-medium text-gray-900">Remove review?</p>
                  <p className="text-xs text-gray-500">
                    This will remove the review by{" "}
                    <span className="font-medium">{review?.reviewed_by}</span> and reset the case to
                    pending.
                  </p>
                  <div className="flex gap-2 justify-end">
                    <button onClick={() => setUnreviewConfirm(false)} className="btn-secondary">
                      Cancel
                    </button>
                    <button onClick={handleUnreview} className="btn-primary">
                      Remove review
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <div className="flex-1 flex min-h-0">
        <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-6">
          <section className="bg-white border border-gray-100 rounded-xl">
            <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">
                Samples
              </p>
              <div className="flex items-center gap-2">
                {(caseData?.has_multiqc as boolean | undefined) && (
                  <div className="flex items-center gap-1 mr-1">
                    {multiqcError && <span className="text-xs text-red-400">Failed to load.</span>}
                    <button
                      onClick={handleOpenMultiqc}
                      disabled={multiqcLoading}
                      className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-full border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors disabled:opacity-50"
                    >
                      <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
                        <path
                          d="M7 3H3v10h10V9M9 2h5v5M13 3l-6 6"
                          stroke="currentColor"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                      {multiqcLoading ? "Loading…" : "MultiQC"}
                    </button>
                    <button
                      onClick={handleDownloadMultiqc}
                      disabled={multiqcLoading}
                      className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-full border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors disabled:opacity-50"
                    >
                      <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
                        <path
                          d="M8 2v8M5 7l3 3 3-3M3 12h10"
                          stroke="currentColor"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                      Download
                    </button>
                  </div>
                )}
                <div className="flex gap-1.5">
                  {FILTERS.map((f) => (
                    <button
                      key={f}
                      onClick={() => setFilter(f)}
                      className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                        filter === f
                          ? "bg-gray-900 text-white font-medium"
                          : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                      }`}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <table className="w-full text-left border-collapse">
              <thead>
                <tr>
                  {["Sample ID", "Material", "Type", "Source", "Total reads"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100 whitespace-nowrap"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => {
                  const trana = s.trana as
                    | { nanoplot_unprocessed?: { number_of_reads?: number } }
                    | undefined;
                  const tp = s.taxprofiler as
                    | { fastp?: { total_reads_before_filtering?: number } }
                    | undefined;
                  return (
                    <tr
                      key={s._id as string}
                      onClick={() => navigate(`/samples/${s._id}`)}
                      className="cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors"
                    >
                      <td className="px-4 py-3 font-mono text-xs text-gray-700">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span>{s.sample_id ?? "—"}</span>
                          {((s.all_taxon_ids as number[] | undefined) ?? [])
                            .filter((id) => id in pathogenMap)
                            .map((id) => (
                              <Link
                                key={id}
                                to={`/taxa/${id}`}
                                title={pathogenMap[id].taxon_name}
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs bg-red-50 text-red-600 font-medium hover:bg-red-100 transition-colors font-sans not-italic"
                              >
                                {pathogenMap[id].taxon_name}
                              </Link>
                            ))}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">
                        {(s.material as string | undefined) ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        <Badge type={(s.sample_type as string | undefined) ?? "sample"} />
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">
                        {(s.sample_source as string | undefined) ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-700">
                        {fmt(
                          trana
                            ? trana.nanoplot_unprocessed?.number_of_reads
                            : tp?.fastp?.total_reads_before_filtering
                        )}
                      </td>
                    </tr>
                  );
                })}
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-sm text-gray-400">
                      No samples match this filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </section>

          {classifiers.length > 0 &&
            (() => {
              const isTrana = samples.some((s) => s.trana);
              return (
                <section className="bg-white border border-gray-100 rounded-xl">
                  <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
                    <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">
                      Classifier results
                    </p>
                    <div className="flex gap-1.5">
                      {classifiers.map((clf) => (
                        <button
                          key={clf.name}
                          onClick={() => {
                            setKronaTab(clf.name);
                            setSearchParams({ classifier: clf.name });
                          }}
                          className={`px-2.5 py-1 rounded-full text-xs transition-colors ${
                            kronaTab === clf.name
                              ? "bg-gray-900 text-white font-medium"
                              : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                          }`}
                        >
                          {clf.name}
                        </button>
                      ))}
                    </div>
                  </div>

                  {classifiers.map(
                    (clf) =>
                      kronaTab === clf.name && (
                        <div key={clf.name}>
                          <div className="px-4 pt-3 pb-1">
                            <p className="text-xs text-gray-300 font-mono">{clf.db}</p>
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
                                    className="px-4 py-2.5 text-xs font-medium text-gray-400 border-b border-gray-100 whitespace-nowrap"
                                  >
                                    {h}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {samples.map((s) => {
                                const topTaxaMap = s.top_taxa as
                                  | Record<string, TopTaxon[]>
                                  | undefined;
                                const topTaxa: TopTaxon[] = topTaxaMap?.[clf.name] ?? [];
                                const topTaxaCell = (
                                  <td className="px-4 py-1.5">
                                    <div className="flex flex-col gap-0">
                                      {topTaxa.map((t, i) => (
                                        <span
                                          key={i}
                                          className="flex items-center gap-1"
                                          style={{ fontSize: "11px", lineHeight: "1.4" }}
                                        >
                                          <span
                                            className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                                              t.superkingdom === "Bacteria"
                                                ? "bg-blue-400"
                                                : t.superkingdom === "Viruses"
                                                  ? "bg-red-400"
                                                  : t.superkingdom === "Eukaryota"
                                                    ? "bg-amber-400"
                                                    : t.superkingdom === "Archaea"
                                                      ? "bg-purple-400"
                                                      : "bg-gray-300"
                                            }`}
                                          />
                                          <span className="text-gray-600 italic truncate max-w-36">
                                            {t.name}
                                          </span>
                                          {t.pct != null && (
                                            <span className="text-gray-400 flex-shrink-0">
                                              {t.pct?.toFixed(1)}%
                                            </span>
                                          )}
                                        </span>
                                      ))}
                                    </div>
                                  </td>
                                );
                                const trana = s.trana as
                                  | { nanoplot_unprocessed?: { number_of_reads?: number } }
                                  | undefined;
                                const tp = s.taxprofiler as
                                  | {
                                      classifiers?: Record<
                                        string,
                                        {
                                          pct_unclassified?: number;
                                          num_species?: number;
                                          num_genera?: number;
                                        }
                                      >;
                                    }
                                  | undefined;
                                const hostPct = s.host_pct as Record<string, number> | undefined;
                                const spikeInMap = s.spike_in_taxa as
                                  | Record<string, TopTaxon[]>
                                  | undefined;
                                return (
                                  <tr
                                    key={s._id as string}
                                    onClick={() =>
                                      navigate(`/samples/${s._id}?classifier=${kronaTab ?? ""}`)
                                    }
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
                                        const clfQc = tp?.classifiers?.[clf.name];
                                        const spikeIn: TopTaxon[] = spikeInMap?.[clf.name] ?? [];
                                        return (
                                          <>
                                            <td className="px-4 py-1.5 text-xs text-gray-700">
                                              {fmtPct(clfQc?.pct_unclassified)}
                                            </td>
                                            <td className="px-4 py-1.5 text-xs text-gray-700">
                                              {hostPct?.[clf.name] != null
                                                ? `${hostPct[clf.name]}%`
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
                                                  {spikeIn.map((t, i) => (
                                                    <span key={i} className="text-gray-600 italic">
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

                          {isTrana
                            ? kronaSelectedSample && (
                                <div className="p-4 border-t border-gray-50">
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
                                    <p className="text-xs text-red-400">
                                      Krona file could not be loaded.
                                    </p>
                                  )}
                                  {kronaUrls[kronaSelectedSample] && (
                                    <iframe
                                      key={kronaUrls[kronaSelectedSample]}
                                      src={kronaUrls[kronaSelectedSample]}
                                      title={`Krona — ${
                                        samples.find((s) => s._id === kronaSelectedSample)
                                          ?.sample_id
                                      }`}
                                      className="w-full rounded-lg border border-gray-100"
                                      style={{ height: "85vh" }}
                                      sandbox="allow-scripts allow-popups allow-forms"
                                    />
                                  )}
                                </div>
                              )
                            : clf.krona_id && (
                                <div className="p-4 border-t border-gray-50">
                                  {kronaErrors[clf.name] && (
                                    <p className="text-xs text-red-400">
                                      Krona file could not be loaded.
                                    </p>
                                  )}
                                  {!kronaUrls[clf.name] && !kronaErrors[clf.name] && (
                                    <div className="flex items-center justify-center h-40 text-sm text-gray-400">
                                      Loading Krona…
                                    </div>
                                  )}
                                  {kronaUrls[clf.name] && (
                                    <iframe
                                      key={kronaUrls[clf.name]}
                                      src={kronaUrls[clf.name]}
                                      title={`Krona — ${clf.name}`}
                                      className="w-full rounded-lg border border-gray-100"
                                      style={{ height: "85vh" }}
                                      sandbox="allow-scripts allow-popups allow-forms"
                                    />
                                  )}
                                </div>
                              )}
                        </div>
                      )
                  )}
                </section>
              );
            })()}

          {caseData && caseData.pipeline_info ? (
            <section className="bg-white border border-gray-100 rounded-xl">
              <button
                onClick={() => setProvenanceOpen((o) => !o)}
                className="w-full flex items-center gap-2 px-4 py-3 text-left hover:bg-gray-50 transition-colors"
              >
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">
                  Provenance
                </p>
                <svg
                  className={`w-3 h-3 text-gray-300 transition-transform ${
                    provenanceOpen ? "rotate-180" : ""
                  }`}
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
              {provenanceOpen &&
                (() => {
                  const pipelineInfo = caseData.pipeline_info as {
                    pipeline_configuration?: Record<string, unknown>;
                    software_used?: Record<string, Record<string, unknown>>;
                  };
                  const pipelineConfig = pipelineInfo.pipeline_configuration ?? {};
                  const toolMap: Record<string, string> = {};
                  Object.values(pipelineInfo.software_used ?? {}).forEach((processTools) => {
                    Object.entries(processTools).forEach(([name, ver]) => {
                      toolMap[String(name)] = String(ver);
                    });
                  });
                  const toolRows = Object.entries(toolMap).sort();

                  const mvInfo = caseData.metaval_pipeline_info as
                    | {
                        pipeline_configuration?: Record<string, unknown>;
                        software_used?: Record<string, Record<string, unknown>>;
                      }
                    | undefined;
                  const mvConfig = mvInfo?.pipeline_configuration ?? {};
                  const mvToolMap: Record<string, string> = {};
                  Object.values(mvInfo?.software_used ?? {}).forEach((processTools) => {
                    Object.entries(processTools).forEach(([name, ver]) => {
                      mvToolMap[String(name)] = String(ver);
                    });
                  });
                  const mvToolRows = Object.entries(mvToolMap).sort();

                  return (
                    <div className="border-t border-gray-100 px-4 py-3 flex flex-col gap-4">
                      <div className="flex flex-col gap-3">
                        <div className="flex gap-6">
                          {pipelineConfig.pipeline_name ? (
                            <span className="text-xs text-gray-500">
                              <span className="text-gray-400">
                                {String(pipelineConfig.pipeline_name)}
                              </span>
                              <span className="font-mono ml-2 text-gray-700">
                                {String(pipelineConfig.pipeline_version)}
                              </span>
                            </span>
                          ) : null}
                          {pipelineConfig.nextflow ? (
                            <span className="text-xs text-gray-500">
                              <span className="text-gray-400">Nextflow</span>
                              <span className="font-mono ml-2 text-gray-700">
                                {String(pipelineConfig.nextflow)}
                              </span>
                            </span>
                          ) : null}
                        </div>
                        <table className="w-full">
                          <thead>
                            <tr>
                              <th className="text-left text-xs font-medium text-gray-400 pb-1.5 w-1/2">
                                Tool
                              </th>
                              <th className="text-left text-xs font-medium text-gray-400 pb-1.5">
                                Version
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {toolRows.map(([name, ver]) => (
                              <tr key={name} className="border-t border-gray-50">
                                <td className="py-1 text-xs text-gray-600">{name}</td>
                                <td className="py-1 font-mono text-xs text-gray-400">{ver}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      {mvInfo && mvToolRows.length > 0 && (
                        <div className="flex flex-col gap-3 border-t border-gray-50 pt-3">
                          <div className="flex gap-6">
                            {mvConfig.pipeline_name ? (
                              <span className="text-xs text-gray-500">
                                <span className="text-gray-400">
                                  {String(mvConfig.pipeline_name)}
                                </span>
                                <span className="font-mono ml-2 text-gray-700">
                                  {String(mvConfig.pipeline_version)}
                                </span>
                              </span>
                            ) : null}
                            {mvConfig.nextflow ? (
                              <span className="text-xs text-gray-500">
                                <span className="text-gray-400">Nextflow</span>
                                <span className="font-mono ml-2 text-gray-700">
                                  {String(mvConfig.nextflow)}
                                </span>
                              </span>
                            ) : null}
                          </div>
                          <table className="w-full">
                            <thead>
                              <tr>
                                <th className="text-left text-xs font-medium text-gray-400 pb-1.5 w-1/2">
                                  Tool
                                </th>
                                <th className="text-left text-xs font-medium text-gray-400 pb-1.5">
                                  Version
                                </th>
                              </tr>
                            </thead>
                            <tbody>
                              {mvToolRows.map(([name, ver]) => (
                                <tr key={name} className="border-t border-gray-50">
                                  <td className="py-1 text-xs text-gray-600">{name}</td>
                                  <td className="py-1 font-mono text-xs text-gray-400">{ver}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  );
                })()}
            </section>
          ) : null}
        </div>

        {notesOpen && (
          <div className="w-80 flex-shrink-0 border-l border-gray-100 flex flex-col bg-white">
            <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
              <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">
                Notes
              </p>
              <button
                onClick={() => setNotesOpen(false)}
                className="text-gray-300 hover:text-gray-500 transition-colors"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
                  <path
                    d="M3 3l10 10M13 3L3 13"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3">
              {notes.length === 0 && (
                <p className="text-xs text-gray-300 text-center py-6">No notes yet.</p>
              )}
              {notes.map((note, i) => {
                // Preserves legacy access pattern: `user` is a username string.
                const currentUsername = (user as unknown as { username?: string } | null)?.username;
                return (
                  <div key={i} className="bg-gray-50 rounded-lg px-3 py-2.5 flex flex-col gap-1">
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-medium text-gray-600">{note.author}</span>
                      <span className="text-gray-200">·</span>
                      <span className="text-xs text-gray-400">
                        {note.created_at
                          ? new Date(note.created_at).toLocaleDateString("sv-SE", {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : ""}
                      </span>
                      {(role === "admin" || note.author === currentUsername) && (
                        <button
                          onClick={() => handleDeleteNote(i)}
                          className="ml-auto text-gray-300 hover:text-red-400 transition-colors"
                        >
                          <svg className="w-3 h-3" viewBox="0 0 16 16" fill="none">
                            <path
                              d="M3 3l10 10M13 3L3 13"
                              stroke="currentColor"
                              strokeWidth="1.5"
                              strokeLinecap="round"
                            />
                          </svg>
                        </button>
                      )}
                    </div>
                    <p className="text-xs text-gray-600 whitespace-pre-wrap">{note.text}</p>
                  </div>
                );
              })}
            </div>

            {role !== "reader" && (
              <div className="px-4 py-3 border-t border-gray-100 flex flex-col gap-2">
                <textarea
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleAddNote();
                  }}
                  placeholder="Write a note…"
                  rows={3}
                  className="w-full text-xs border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-blue-300 resize-none"
                />
                <button
                  onClick={handleAddNote}
                  disabled={noteSaving || !noteText.trim()}
                  className="btn-primary disabled:opacity-50 text-xs"
                >
                  {noteSaving ? "Saving…" : "Add note"}
                </button>
                <p className="text-xs text-gray-300 text-center">⌘↵ to save</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
