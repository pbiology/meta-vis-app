interface DataWarningProps {
  message: string;
}

// Inline amber warning banner for partial data-load failures (e.g. an auxiliary
// endpoint 500'd but the page is still usable). Used by SampleDetail and
// related views.
export default function DataWarning({ message }: Readonly<DataWarningProps>) {
  return <p className="text-xs text-amber-600 bg-amber-50 rounded px-3 py-1.5 mb-2">{message}</p>;
}
