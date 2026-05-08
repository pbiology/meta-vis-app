import { useTaxonExternalLinks } from "../../hooks/queries/useTaxa";
import type { ExternalLink } from "./types";

interface ExternalLinksSectionProps {
  taxonId: number;
}

export default function ExternalLinksSection({ taxonId }: Readonly<ExternalLinksSectionProps>) {
  const { data, isLoading } = useTaxonExternalLinks(taxonId);
  const links = (data as { links?: ExternalLink[] } | undefined)?.links ?? [];

  if (isLoading) {
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
  }

  if (links.length === 0) return null;

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <div className="px-4 py-3 border-b border-gray-100">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider">
          External resources
        </p>
      </div>
      <div className="px-4 py-3 flex flex-wrap gap-2">
        {links.map((link) => (
          <a
            key={link.url}
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
