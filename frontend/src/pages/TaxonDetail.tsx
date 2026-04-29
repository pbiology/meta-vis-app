import React, { useState, useEffect, useRef } from "react";
import { useNavigate, Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  getTaxon,
  getTaxonOccurrences,
  updateClinicalNotes,
  getTaxonExternalLinks,
  getTaxonLiterature,
  getBvbrcGenomes,
  getBvbrcSpecialtyGenes,
} from "../api/taxa";
import { getPathogens } from "../api/alerts";
import { useAuth } from "../context/AuthContext";
import { useReportBuilder } from "../context/ReportBuilderContext";
import { fmt } from "../utils/format";
import { useRequiredParam } from "../utils/routeParams";

const KINGDOM_COLOURS: Record<string, string> = {
  Viruses: "text-red-600",
  Bacteria: "text-blue-600",
  Eukaryota: "text-amber-600",
  Archaea: "text-purple-600",
};

interface TaxonDoc {
  taxon_id: number;
  name?: string;
  rank?: string;
  species?: string;
  genus?: string;
  family?: string;
  order?: string;
  class?: string;
  phylum?: string;
  kingdom?: string;
  superkingdom?: string;
  ncbi_url?: string;
  clinical_notes?: string | null;
  clinical_notes_author?: string | null;
  clinical_notes_updated_at?: string | null;
  needs_taxonomy_refresh?: boolean;
  taxdump_version?: string;
  [key: string]: unknown;
}

interface OccurrenceSample {
  sample_id: string;
  reads?: Record<string, number | null | undefined>;
}

interface OccurrenceCase {
  case_id: string;
  order_date?: string | null;
  sample_count: number;
  classifiers?: string[];
  samples: OccurrenceSample[];
}

interface OccurrencesData {
  total_cases: number;
  all_classifiers?: string[];
  cases: OccurrenceCase[];
}

interface ExternalLink {
  name: string;
  url: string;
}

interface LiteratureArticle {
  pmid: string | number;
  title: string;
  journal?: string;
  pub_date?: string;
  link: string;
}

interface IsolationSource {
  source: string;
  count: number;
}
interface CountryCount {
  country: string;
  count: number;
}
interface AmrPhenotypeGenome {
  antibiotic: string;
  count: number;
}
interface GenomesData {
  total_genomes: number;
  bvbrc_url: string;
  isolation_sources: IsolationSource[];
  countries: CountryCount[];
  amr_phenotypes: AmrPhenotypeGenome[];
}

interface AmrGene {
  gene?: string;
  antibiotics?: string[];
  antibiotics_class?: string;
  source?: string;
  pmid?: (string | number)[];
}
interface VirulenceFactor {
  gene?: string;
  product?: string;
  source?: string;
  pmid?: (string | number)[];
}
interface AmrPhenotype {
  antibiotic: string;
  resistant: number;
  susceptible: number;
}
interface SpecialtyData {
  amr_genes: AmrGene[];
  virulence_factors: VirulenceFactor[];
  amr_phenotypes: AmrPhenotype[];
  bvbrc_url?: string;
}

interface LineageRowProps {
  label: string;
  value?: string | null;
}

function LineageRow({ label, value }: LineageRowProps) {
  if (!value) return null;
  return (
    <div className="flex items-baseline gap-2 py-1 border-b border-gray-50 last:border-0">
      <span className="text-xs text-gray-400 w-24 flex-shrink-0">{label}</span>
      <span className="text-xs text-gray-700 italic">{value}</span>
    </div>
  );
}

function RefreshWarning() {
  return (
    <div className="flex items-start gap-2.5 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-700">
      <svg className="w-4 h-4 flex-shrink-0 mt-0.5" viewBox="0 0 16 16" fill="none">
        <path
          d="M8 2L14 13H2L8 2z"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinejoin="round"
        />
        <path d="M8 6v3M8 11v.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      </svg>
      <span>
        Full taxonomy data for this taxon has not been loaded yet. Run{" "}
        <code className="font-mono bg-amber-100 px-1 rounded">load_taxonomy.py</code> to populate
        lineage and rank information.
      </span>
    </div>
  );
}

interface ClinicalNotesEditorProps {
  taxonId: number;
  initialNotes?: string | null;
  notesAuthor?: string | null;
  notesUpdatedAt?: string | null;
  canEdit: boolean;
}

function ClinicalNotesEditor({
  taxonId,
  initialNotes,
  notesAuthor,
  notesUpdatedAt,
  canEdit,
}: ClinicalNotesEditorProps) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState<string>(initialNotes ?? "");
  const [author, setAuthor] = useState<string | null>(notesAuthor ?? null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(notesUpdatedAt ?? null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { user: currentUsername } = useAuth();
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (editing && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [editing]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await updateClinicalNotes(taxonId, value.trim() || null);
      if (value.trim()) {
        setAuthor(currentUsername);
        setUpdatedAt(new Date().toISOString());
      } else {
        setAuthor(null);
        setUpdatedAt(null);
      }
      setEditing(false);
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    setValue(initialNotes ?? "");
    setEditing(false);
    setError(null);
  }

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">
          Clinical notes
        </p>
        {canEdit && !editing && (
          <button
            onClick={() => setEditing(true)}
            className="text-xs px-2.5 py-1 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
          >
            {value ? "Edit" : "Add notes"}
          </button>
        )}
      </div>
      <div className="px-4 py-3">
        {editing ? (
          <div className="flex flex-col gap-2">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              rows={5}
              className="w-full text-xs text-gray-700 border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-blue-300 resize-none"
              placeholder="Add clinical context, known disease associations, relevant notes…"
            />
            {error && <p className="text-xs text-red-400">{error}</p>}
            <div className="flex gap-2 justify-end">
              <button
                onClick={handleCancel}
                className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="text-xs px-3 py-1.5 rounded-lg bg-gray-900 text-white hover:bg-gray-700 transition-colors disabled:opacity-50"
              >
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </div>
        ) : value ? (
          <div className="flex flex-col gap-2">
            <p className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">{value}</p>
            {author && (
              <p className="text-xs text-gray-300">
                Last updated by <span className="text-gray-400 font-medium">{author}</span>
                {updatedAt && (
                  <>
                    {" "}
                    on{" "}
                    <span className="text-gray-400">
                      {new Date(updatedAt).toLocaleDateString(undefined, {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  </>
                )}
              </p>
            )}
          </div>
        ) : (
          <p className="text-xs text-gray-300 italic">No clinical notes recorded.</p>
        )}
      </div>
    </section>
  );
}

function OccurrencesSection({ taxonId }: { taxonId: number }) {
  const [windowDays, setWindowDays] = useState(90);
  const [data, setData] = useState<OccurrencesData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getTaxonOccurrences(taxonId, windowDays)
      .then((d) => setData(d as unknown as OccurrencesData))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [taxonId, windowDays]);

  const WINDOWS = [30, 90, 180, 365];

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

      {loading ? (
        <div className="px-4 py-8 text-xs text-gray-400 text-center">Loading…</div>
      ) : !data || data.total_cases === 0 ? (
        <div className="px-4 py-8 text-xs text-gray-300 text-center">
          Not detected in any case in the last {windowDays} days.
        </div>
      ) : (
        <>
          <div className="px-4 py-2.5 border-b border-gray-50 flex items-center gap-2">
            <span className="text-xs text-gray-400">
              Detected in <span className="font-medium text-gray-700">{data.total_cases}</span>{" "}
              {data.total_cases === 1 ? "case" : "cases"} in the last {windowDays} days
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
                {data.cases.map((c, i) => {
                  const classifiers = data.all_classifiers ?? c.classifiers ?? [];
                  const gridCols = `minmax(0, auto) repeat(${classifiers.length}, minmax(0, 1fr))`;
                  return (
                    <tr key={i} className="border-t border-gray-50 hover:bg-gray-50 align-top">
                      <td className="px-4 py-2.5">
                        <Link
                          to={`/cases/${c.case_id}`}
                          className="text-xs font-mono text-blue-600 hover:underline"
                        >
                          {c.case_id}
                        </Link>
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

function ExternalLinksSection({ taxonId }: { taxonId: number }) {
  const [links, setLinks] = useState<ExternalLink[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTaxonExternalLinks(taxonId)
      .then((data) =>
        setLinks(((data as { links?: ExternalLink[] }).links ?? []) as ExternalLink[])
      )
      .catch(() => setLinks([]))
      .finally(() => setLoading(false));
  }, [taxonId]);

  if (loading)
    return (
      <section className="bg-white border border-gray-100 rounded-xl">
        <div className="px-4 py-3 border-b border-gray-100">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
            External resources
          </p>
        </div>
        <div className="px-4 py-6 text-xs text-gray-400 text-center">Loading…</div>
      </section>
    );

  if (!links || links.length === 0) return null;

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <div className="px-4 py-3 border-b border-gray-100">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
          External resources
        </p>
      </div>
      <div className="px-4 py-3 flex flex-wrap gap-2">
        {links.map((link, i) => (
          <a
            key={i}
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:border-blue-300 hover:text-blue-600 transition-colors"
          >
            {link.name}
            <svg className="w-2.5 h-2.5 opacity-50" viewBox="0 0 16 16" fill="none">
              <path
                d="M6 3H3v10h10v-3M13 3H9m4 0v4m0-4L7 9"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </a>
        ))}
      </div>
    </section>
  );
}

function LiteratureSection({ taxonId }: { taxonId: number }) {
  const [articles, setArticles] = useState<LiteratureArticle[]>([]);
  const [pubmedQuery, setPubmedQuery] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [maxResults, setMaxResults] = useState(5);
  const [collapsed, setCollapsed] = useState(false);
  const [queryVisible, setQueryVisible] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    getTaxonLiterature(taxonId, maxResults)
      .then((data) => {
        const d = data as { articles?: LiteratureArticle[]; pubmed_query?: string };
        setArticles(d.articles ?? []);
        setPubmedQuery(d.pubmed_query ?? null);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [taxonId, maxResults]);

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center gap-2 px-4 py-3 border-b border-gray-100 hover:bg-gray-50 transition-colors"
      >
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1 text-left">
          Clinical literature
        </p>
        <svg
          className={`w-3.5 h-3.5 text-gray-300 transition-transform ${collapsed ? "-rotate-90" : ""}`}
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

      {!collapsed && loading ? (
        <div className="px-4 py-8 text-xs text-gray-400 text-center">Loading…</div>
      ) : !collapsed && error ? (
        <div className="px-4 py-6 text-xs text-gray-400 text-center">
          Could not retrieve literature. Check network connectivity.
        </div>
      ) : !collapsed && articles.length === 0 ? (
        <div className="px-4 py-6 text-xs text-gray-300 text-center italic">
          No case reports or outbreak publications found in PubMed.
        </div>
      ) : !collapsed ? (
        <>
          <ul className="divide-y divide-gray-50">
            {articles.map((a) => (
              <li key={a.pmid} className="px-4 py-3 flex flex-col gap-0.5">
                <a
                  href={a.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:underline leading-snug"
                >
                  {a.title}
                </a>
                <p className="text-xs text-gray-400">
                  {a.journal}
                  {a.pub_date ? <span className="text-gray-300"> · {a.pub_date}</span> : null}
                </p>
              </li>
            ))}
          </ul>
          {maxResults < 20 && (
            <div className="px-4 py-3 border-t border-gray-50">
              <button
                onClick={() => setMaxResults((n) => Math.min(n + 10, 20))}
                className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
              >
                Show more
              </button>
            </div>
          )}
          {pubmedQuery && (
            <div className="px-4 py-3 border-t border-gray-50">
              <button
                onClick={() => setQueryVisible((v) => !v)}
                className="flex items-center gap-1 text-xs text-gray-300 hover:text-gray-500 transition-colors"
              >
                <svg
                  className={`w-3 h-3 transition-transform ${queryVisible ? "rotate-90" : ""}`}
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
                PubMed query
              </button>
              {queryVisible && (
                <pre className="mt-2 text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-2 whitespace-pre-wrap break-all font-mono leading-relaxed">
                  {pubmedQuery}
                </pre>
              )}
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}

function PubmedLinks({ pmids }: { pmids?: (string | number)[] }) {
  if (!pmids || pmids.length === 0) return <span className="text-gray-300">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {pmids.map((id) => (
        <a
          key={id}
          href={`https://pubmed.ncbi.nlm.nih.gov/${id}/`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-500 hover:underline tabular-nums"
        >
          {id}
        </a>
      ))}
    </div>
  );
}

interface SpecialtyGenesSubsectionProps {
  specialty: SpecialtyData | null;
  loadingSpecialty: boolean;
}

function SpecialtyGenesSubsection({ specialty, loadingSpecialty }: SpecialtyGenesSubsectionProps) {
  const [sgCollapsed, setSgCollapsed] = useState(true);

  const hasSpecialtyData =
    specialty &&
    (specialty.amr_genes.length > 0 ||
      specialty.virulence_factors.length > 0 ||
      specialty.amr_phenotypes.length > 0);

  const amrCount = specialty?.amr_genes?.length ?? 0;
  const vfCount = specialty?.virulence_factors?.length ?? 0;

  function HeaderSummary() {
    if (loadingSpecialty) return null;
    if (!hasSpecialtyData)
      return <span className="text-xs text-gray-300 italic">No data in BV-BRC</span>;
    return (
      <div className="flex items-center gap-2">
        {amrCount > 0 && (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-red-600">
            <svg className="w-3 h-3 flex-shrink-0" viewBox="0 0 16 16" fill="none">
              <path
                d="M8 1.5L2 4v4c0 3.3 2.5 5.8 6 7 3.5-1.2 6-3.7 6-7V4L8 1.5z"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinejoin="round"
              />
              <path
                d="M5.5 8l1.8 1.8L10.5 6"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            {amrCount} AMR {amrCount === 1 ? "gene" : "genes"}
          </span>
        )}
        {vfCount > 0 && (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-600">
            <svg className="w-3 h-3 flex-shrink-0" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="1.5" stroke="currentColor" strokeWidth="1.4" />
              <path
                d="M8 6.5C8 4.6 6.4 3 4.5 3S1 4.6 1 6.5c0 1.4.8 2.6 2 3.2M8 6.5C8 4.6 9.6 3 11.5 3S15 4.6 15 6.5c0 1.4-.8 2.6-2 3.2M5 12.5c.9.5 1.9.8 3 .8s2.1-.3 3-.8"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
              />
            </svg>
            {vfCount} virulence {vfCount === 1 ? "factor" : "factors"}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="border-t border-gray-50">
      <button
        onClick={() => setSgCollapsed((c) => !c)}
        className="w-full flex items-center gap-2 px-4 py-3 hover:bg-gray-50 transition-colors"
      >
        <p className="text-xs font-medium text-gray-500 flex-shrink-0">Specialty genes</p>
        <div className="flex-1 flex justify-start">
          <HeaderSummary />
        </div>
        <svg
          className={`w-3 h-3 text-gray-300 flex-shrink-0 transition-transform ${sgCollapsed ? "-rotate-90" : ""}`}
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

      {!sgCollapsed && hasSpecialtyData && specialty && (
        <div className="px-4 pb-3">
          {loadingSpecialty ? (
            <p className="text-xs text-gray-400">Loading…</p>
          ) : (
            <div className="flex flex-col gap-4">
              {specialty.amr_genes.length > 0 && (
                <div>
                  <p className="text-xs text-gray-400 mb-1">
                    AMR genes ({specialty.amr_genes.length})
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left">
                      <thead>
                        <tr>
                          {["Gene", "Antibiotics", "Class", "Source", "PubMed"].map((h) => (
                            <th
                              key={h}
                              className="px-3 py-1.5 text-xs font-medium text-gray-400 border-b border-gray-100"
                            >
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {specialty.amr_genes.map((g, i) => (
                          <tr key={i} className="border-t border-gray-50 hover:bg-gray-50">
                            <td className="px-3 py-1.5 text-xs font-mono text-gray-700">
                              {g.gene || "—"}
                            </td>
                            <td className="px-3 py-1.5 text-xs text-gray-500">
                              {g.antibiotics && g.antibiotics.length > 0
                                ? g.antibiotics.join(", ")
                                : "—"}
                            </td>
                            <td className="px-3 py-1.5 text-xs text-gray-500">
                              {g.antibiotics_class || "—"}
                            </td>
                            <td className="px-3 py-1.5 text-xs text-gray-400">{g.source || "—"}</td>
                            <td className="px-3 py-1.5">
                              <PubmedLinks pmids={g.pmid} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {specialty.virulence_factors.length > 0 && (
                <div>
                  <p className="text-xs text-gray-400 mb-1">
                    Virulence factors ({specialty.virulence_factors.length})
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left">
                      <thead>
                        <tr>
                          {["Gene", "Product", "Source", "PubMed"].map((h) => (
                            <th
                              key={h}
                              className="px-3 py-1.5 text-xs font-medium text-gray-400 border-b border-gray-100"
                            >
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {specialty.virulence_factors.map((g, i) => (
                          <tr key={i} className="border-t border-gray-50 hover:bg-gray-50">
                            <td className="px-3 py-1.5 text-xs font-mono text-gray-700">
                              {g.gene || "—"}
                            </td>
                            <td className="px-3 py-1.5 text-xs text-gray-500">
                              {g.product || "—"}
                            </td>
                            <td className="px-3 py-1.5 text-xs text-gray-400">{g.source || "—"}</td>
                            <td className="px-3 py-1.5">
                              <PubmedLinks pmids={g.pmid} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {specialty.amr_phenotypes.length > 0 && (
                <div>
                  <p className="text-xs text-gray-400 mb-1">
                    AMR phenotypes ({specialty.amr_phenotypes.length} antibiotics)
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left">
                      <thead>
                        <tr>
                          {["Antibiotic", "Resistant", "Susceptible"].map((h) => (
                            <th
                              key={h}
                              className="px-3 py-1.5 text-xs font-medium text-gray-400 border-b border-gray-100"
                            >
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {specialty.amr_phenotypes.map((p, i) => (
                          <tr key={i} className="border-t border-gray-50 hover:bg-gray-50">
                            <td className="px-3 py-1.5 text-xs text-gray-700">{p.antibiotic}</td>
                            <td className="px-3 py-1.5 text-xs tabular-nums text-red-600">
                              {p.resistant}
                            </td>
                            <td className="px-3 py-1.5 text-xs tabular-nums text-green-600">
                              {p.susceptible}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {specialty.bvbrc_url && (
                <div>
                  <ExternalLinkButton href={specialty.bvbrc_url}>View in BV-BRC</ExternalLinkButton>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface ExternalLinkButtonProps {
  href: string;
  children: React.ReactNode;
}

function ExternalLinkButton({ href, children }: ExternalLinkButtonProps) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:border-blue-300 hover:text-blue-600 transition-colors"
    >
      {children}
      <svg className="w-2.5 h-2.5 opacity-50" viewBox="0 0 16 16" fill="none">
        <path
          d="M6 3H3v10h10v-3M13 3H9m4 0v4m0-4L7 9"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </a>
  );
}

function BvbrcSection({ taxonId }: { taxonId: number }) {
  const [genomes, setGenomes] = useState<GenomesData | null>(null);
  const [specialty, setSpecialty] = useState<SpecialtyData | null>(null);
  const [loadingGenomes, setLoadingGenomes] = useState(true);
  const [loadingSpecialty, setLoadingSpecialty] = useState(true);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    getBvbrcGenomes(taxonId)
      .then((d) => setGenomes(d as unknown as GenomesData))
      .catch(() => setGenomes(null))
      .finally(() => setLoadingGenomes(false));

    getBvbrcSpecialtyGenes(taxonId)
      .then((d) => setSpecialty(d as unknown as SpecialtyData))
      .catch(() => setSpecialty(null))
      .finally(() => setLoadingSpecialty(false));
  }, [taxonId]);

  const hasGenomeData = genomes && genomes.total_genomes > 0;

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center gap-2 px-4 py-3 border-b border-gray-100 hover:bg-gray-50 transition-colors"
      >
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1 text-left">
          BV-BRC resources
        </p>
        <svg
          className={`w-3.5 h-3.5 text-gray-300 transition-transform ${collapsed ? "-rotate-90" : ""}`}
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

      {!collapsed && (
        <div className="divide-y divide-gray-50">
          <div className="px-4 py-3">
            <p className="text-xs font-medium text-gray-500 mb-2">Sequenced genomes</p>
            {loadingGenomes ? (
              <p className="text-xs text-gray-400">Loading…</p>
            ) : !hasGenomeData || !genomes ? (
              <p className="text-xs text-gray-300 italic">No genome data found in BV-BRC.</p>
            ) : (
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-lg font-semibold text-gray-800 tabular-nums">
                    {genomes.total_genomes.toLocaleString()}
                  </span>
                  <span className="text-xs text-gray-400">genomes in BV-BRC</span>
                  <ExternalLinkButton href={genomes.bvbrc_url}>View all</ExternalLinkButton>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {genomes.isolation_sources.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-400 mb-1">Top isolation sources</p>
                      <ul className="space-y-0.5">
                        {genomes.isolation_sources.map((s, i) => (
                          <li key={i} className="flex items-baseline justify-between gap-2">
                            <span className="text-xs text-gray-600 truncate">{s.source}</span>
                            <span className="text-xs text-gray-400 tabular-nums flex-shrink-0">
                              {s.count}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {genomes.countries.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-400 mb-1">Top countries</p>
                      <ul className="space-y-0.5">
                        {genomes.countries.map((c, i) => (
                          <li key={i} className="flex items-baseline justify-between gap-2">
                            <span className="text-xs text-gray-600 truncate">{c.country}</span>
                            <span className="text-xs text-gray-400 tabular-nums flex-shrink-0">
                              {c.count}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {genomes.amr_phenotypes.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-400 mb-1">Resistant to (genomes count)</p>
                    <div className="flex flex-wrap gap-1.5">
                      {genomes.amr_phenotypes.map((a, i) => (
                        <span
                          key={i}
                          className="text-xs px-2 py-0.5 bg-red-50 text-red-600 rounded-full"
                          title={`${a.count} genome(s) resistant`}
                        >
                          {a.antibiotic} ({a.count})
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          <SpecialtyGenesSubsection specialty={specialty} loadingSpecialty={loadingSpecialty} />
        </div>
      )}
    </section>
  );
}

export default function TaxonDetail() {
  const taxonIdParam = useRequiredParam("taxonId");
  const { sampleId } = useParams<{ sampleId?: string }>();
  const navigate = useNavigate();
  const { role } = useAuth();
  const { isSelected, addTaxon, removeTaxon } = useReportBuilder();

  const [taxon, setTaxon] = useState<TaxonDoc | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const canEdit = role === "writer" || role === "admin";

  const { data: pathogenList = [] } = useQuery({
    queryKey: ["pathogens"],
    queryFn: () => getPathogens(),
  });

  useEffect(() => {
    getTaxon(Number(taxonIdParam))
      .then((t) => setTaxon(t as TaxonDoc))
      .catch(() => setError("Taxon not found. Run load_taxonomy.py to populate reference data."))
      .finally(() => setLoading(false));
  }, [taxonIdParam]);

  if (loading)
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">Loading…</div>
    );

  if (error || !taxon)
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <p className="text-sm text-gray-500">{error}</p>
        <button
          onClick={() => navigate(-1)}
          className="text-xs text-gray-400 hover:text-gray-600 underline"
        >
          Go back
        </button>
      </div>
    );

  const nameColour = (taxon.superkingdom && KINGDOM_COLOURS[taxon.superkingdom]) ?? "text-gray-900";

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100 flex-shrink-0">
        <button
          onClick={() => navigate(-1)}
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
          Back
        </button>
        <span className="text-gray-200">/</span>
        <h1 className={`text-sm font-medium italic flex-1 ${nameColour}`}>{taxon.name}</h1>
        <a
          href={taxon.ncbi_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-gray-400 hover:text-blue-500 font-mono transition-colors"
          title="Open in NCBI Taxonomy Browser"
        >
          taxid:{taxon.taxon_id}
        </a>
        {sampleId && (() => {
          const selected = isSelected(sampleId, taxon.taxon_id);
          return (
            <button
              onClick={() =>
                selected
                  ? removeTaxon(sampleId, taxon.taxon_id)
                  : addTaxon(sampleId, taxon.taxon_id)
              }
              className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                selected
                  ? "border-blue-300 bg-blue-50 text-blue-700 hover:bg-blue-100"
                  : "border-gray-200 text-gray-500 hover:bg-gray-50"
              }`}
            >
              {selected ? "In report ✓" : "Add to report"}
            </button>
          );
        })()}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-5">
        {taxon.needs_taxonomy_refresh && <RefreshWarning />}

        {(() => {
          const pathogen = pathogenList.find((p) => p.taxon_id === Number(taxonIdParam)) as
            | { taxon_id: number; notes?: string | null }
            | undefined;
          if (!pathogen) return null;
          return (
            <div className="flex items-start gap-2.5 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700">
              <svg className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" viewBox="0 0 16 16" fill="none">
                <circle cx="8" cy="8" r="5.5" stroke="currentColor" strokeWidth="1.3" />
                <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.3" />
                <path
                  d="M8 2.5v1.5M8 12v1.5M2.5 8h1.5M12 8h1.5"
                  stroke="currentColor"
                  strokeWidth="1.3"
                  strokeLinecap="round"
                />
              </svg>
              <span>
                <span className="font-medium">Known pathogen.</span>
                {pathogen.notes && <> {pathogen.notes}</>}
              </span>
            </div>
          );
        })()}

        <section className="bg-white border border-gray-100 rounded-xl p-4">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-3">
            Taxonomy
          </p>
          <div className="grid grid-cols-2 gap-x-8">
            <div>
              <LineageRow label="Rank" value={taxon.rank} />
              <LineageRow label="Species" value={taxon.species} />
              <LineageRow label="Genus" value={taxon.genus} />
              <LineageRow label="Family" value={taxon.family} />
              <LineageRow label="Order" value={taxon.order} />
            </div>
            <div>
              <LineageRow label="Class" value={taxon.class} />
              <LineageRow label="Phylum" value={taxon.phylum} />
              <LineageRow label="Kingdom" value={taxon.kingdom} />
              <LineageRow label="Superkingdom" value={taxon.superkingdom} />
            </div>
          </div>
          {taxon.taxdump_version && (
            <p className="text-xs text-gray-300 mt-3">
              Taxonomy loaded from NCBI dump dated {taxon.taxdump_version}
            </p>
          )}
        </section>

        <ClinicalNotesEditor
          taxonId={taxon.taxon_id}
          initialNotes={taxon.clinical_notes}
          notesAuthor={taxon.clinical_notes_author}
          notesUpdatedAt={taxon.clinical_notes_updated_at}
          canEdit={canEdit}
        />

        <ExternalLinksSection taxonId={taxon.taxon_id} />

        <BvbrcSection taxonId={taxon.taxon_id} />

        <LiteratureSection taxonId={taxon.taxon_id} />

        <OccurrencesSection taxonId={taxon.taxon_id} />
      </div>
    </div>
  );
}
