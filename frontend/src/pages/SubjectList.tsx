import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useSubjects } from "../hooks/queries/useSubjects";

const POLL_MS = 30_000;

const SEX_LABELS: Record<string, string> = {
  F: "Female",
  M: "Male",
  X: "Other",
  unknown: "—",
};

export default function SubjectList() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");

  const subjectsQ = useSubjects({ page, search }, { refetchInterval: POLL_MS });
  const data = subjectsQ.data ?? { items: [], total: 0, pages: 1, page: 1 };
  const subjects = data.items ?? [];
  const isLoading = subjectsQ.isLoading;
  const isError = subjectsQ.isError;

  function handleSearch(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setPage(1);
    setSearch(searchInput);
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 bg-white border-b border-gray-100">
        <h1 className="text-sm font-medium text-gray-900 flex-1">Subjects</h1>
        <form
          onSubmit={handleSearch}
          className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5 w-56"
        >
          <svg className="w-3 h-3 text-gray-400 flex-shrink-0" viewBox="0 0 16 16" fill="none">
            <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5" />
            <path d="M11 11l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            type="text"
            placeholder="Search subject ID…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="bg-transparent text-xs text-gray-700 placeholder-gray-400 outline-none w-full"
          />
        </form>
        <div className="ml-auto pl-3 border-l border-gray-200 flex items-center gap-4">
          <span className="text-xs text-gray-300">{data.total} total</span>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {isLoading && (
          <div className="flex items-center justify-center h-40 text-sm text-gray-400">
            Loading…
          </div>
        )}
        {isError && (
          <div className="flex items-center justify-center h-40 text-sm text-red-500">
            Failed to load subjects.
          </div>
        )}
        {!isLoading && !isError && (
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 bg-white z-10">
              <tr>
                {["Subject ID", "Sex", "Shotgun analyses", "Amplicon analyses"].map((h) => (
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
              {subjects.map((s) => (
                <tr
                  key={s.subject_id}
                  onClick={() => navigate(`/subjects/${s.subject_id}`)}
                  className="cursor-pointer border-b border-gray-50 hover:bg-gray-50 transition-colors"
                >
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">{s.subject_id}</td>
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {SEX_LABELS[s.sex] ?? s.sex}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {s.shotgun_count}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 whitespace-nowrap">
                    {s.amplicon_count}
                  </td>
                </tr>
              ))}
              {subjects.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-10 text-center text-sm text-gray-400">
                    No subjects found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {data.pages > 1 && (
        <div className="flex items-center justify-center gap-3 px-6 py-3 border-t border-gray-100 bg-white flex-shrink-0">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="text-xs px-3 py-1.5 border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors"
          >
            ← Prev
          </button>
          <span className="text-xs text-gray-400">
            Page {page} of {data.pages} · {data.total} subjects
          </span>
          <button
            onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
            disabled={page === data.pages}
            className="text-xs px-3 py-1.5 border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50 transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
