import type { ReactNode } from "react";

interface ExternalLinkButtonProps {
  href: string;
  children: ReactNode;
}

export default function ExternalLinkButton({ href, children }: Readonly<ExternalLinkButtonProps>) {
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
