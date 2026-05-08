import { useState } from "react";
import { useTaxonLiterature } from "../../hooks/queries/useTaxa";
import type { LiteratureArticle } from "./types";

interface LiteratureArticleListProps {
  articles: LiteratureArticle[];
  maxResults: number;
  pubmedQuery: string | null;
  onShowMore: () => void;
}

function LiteratureArticleList({
  articles,
  maxResults,
  pubmedQuery,
  onShowMore,
}: Readonly<LiteratureArticleListProps>) {
  const [queryVisible, setQueryVisible] = useState(false);
  return (
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
            onClick={onShowMore}
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
  );
}

interface LiteratureSectionProps {
  taxonId: number;
}

export default function LiteratureSection({ taxonId }: Readonly<LiteratureSectionProps>) {
  const [maxResults, setMaxResults] = useState(5);
  const [collapsed, setCollapsed] = useState(false);
  const { data, isLoading, isError } = useTaxonLiterature(taxonId, maxResults);
  const lit = data as { articles?: LiteratureArticle[]; pubmed_query?: string } | undefined;
  const articles = lit?.articles ?? [];
  const pubmedQuery = lit?.pubmed_query ?? null;

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

      {!collapsed && (
        <>
          {isLoading && <div className="px-4 py-8 text-xs text-gray-400 text-center">Loading…</div>}
          {!isLoading && isError && (
            <div className="px-4 py-6 text-xs text-gray-400 text-center">
              Could not retrieve literature. Check network connectivity.
            </div>
          )}
          {!isLoading && !isError && articles.length === 0 && (
            <div className="px-4 py-6 text-xs text-gray-300 text-center italic">
              No case reports or outbreak publications found in PubMed.
            </div>
          )}
          {!isLoading && !isError && articles.length > 0 && (
            <LiteratureArticleList
              articles={articles}
              maxResults={maxResults}
              pubmedQuery={pubmedQuery}
              onShowMore={() => setMaxResults((n) => Math.min(n + 10, 20))}
            />
          )}
        </>
      )}
    </section>
  );
}
