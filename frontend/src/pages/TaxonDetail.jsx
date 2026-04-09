import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  getTaxon,
  getTaxonOccurrences,
  updateClinicalNotes,
  getTaxonExternalLinks,
  getTaxonLiterature,
} from "../api/taxa";
import { useAuth } from "../context/AuthContext";

function fmt(n) {
  if (n === undefined || n === null) return "—";
  return typeof n === "number" ? n.toLocaleString() : n;
}

const KINGDOM_COLOURS = {
  Viruses: "text-red-600",
  Bacteria: "text-blue-600",
  Eukaryota: "text-amber-600",
  Archaea: "text-purple-600",
};

function LineageRow({ label, value }) {
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

function ClinicalNotesEditor({ taxonId, initialNotes, notesAuthor, notesUpdatedAt, canEdit }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(initialNotes ?? "");
  const [author, setAuthor] = useState(notesAuthor ?? null);
  const [updatedAt, setUpdatedAt] = useState(notesUpdatedAt ?? null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const { user: currentUsername } = useAuth();
  const textareaRef = useRef(null);

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

function OccurrencesSection({ taxonId }) {
  const [windowDays, setWindowDays] = useState(90);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getTaxonOccurrences(taxonId, windowDays)
      .then(setData)
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
                  {["Case", "Order date", "Samples", "Classifiers / reads"].map((h) => (
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
                {data.cases.map((c, i) => (
                  <tr key={i} className="border-t border-gray-50 hover:bg-gray-50">
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
                      <div className="flex flex-wrap gap-1.5">
                        {c.samples.map((s, j) => (
                          <span
                            key={j}
                            className="text-xs text-gray-500 tabular-nums"
                            title={s.sample_id}
                          >
                            <span className="text-gray-400">{s.classifier}</span> {fmt(s.abundance)}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

function ExternalLinksSection({ taxonId }) {
  const [links, setLinks] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTaxonExternalLinks(taxonId)
      .then((data) => setLinks(data.links ?? []))
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

function LiteratureSection({ taxonId }) {
  const [articles, setArticles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [maxResults, setMaxResults] = useState(5);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(false);
    getTaxonLiterature(taxonId, maxResults)
      .then((data) => setArticles(data.articles ?? []))
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
        </>
      ) : null}
    </section>
  );
}

export default function TaxonDetail() {
  const { taxonId } = useParams();
  const navigate = useNavigate();
  const { role } = useAuth();

  const [taxon, setTaxon] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const canEdit = role === "writer" || role === "admin";

  useEffect(() => {
    getTaxon(Number(taxonId))
      .then(setTaxon)
      .catch(() => setError("Taxon not found. Run load_taxonomy.py to populate reference data."))
      .finally(() => setLoading(false));
  }, [taxonId]);

  if (loading)
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">Loading…</div>
    );

  if (error)
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

  const nameColour = KINGDOM_COLOURS[taxon.superkingdom] ?? "text-gray-900";

  return (
    <div className="flex flex-col h-full">
      {/* Topbar */}
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
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5 flex flex-col gap-5">
        {taxon.needs_taxonomy_refresh && <RefreshWarning />}

        {/* Identity */}
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

        <LiteratureSection taxonId={taxon.taxon_id} />

        <OccurrencesSection taxonId={taxon.taxon_id} />
      </div>
    </div>
  );
}
