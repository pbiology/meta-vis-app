import { useEffect, useState } from "react";
import type { Sample } from "../../../api/types";
import { getCaseKronaUrl } from "../../../api/cases";
import { getKronaUrl } from "../../../api/samples";
import type { Classifier } from "./CaseClassifiers";

interface CaseClassifierKronaProps {
  caseId: string;
  classifiers: Classifier[];
  samples: Sample[];
  activeClassifier: Classifier;
  isTrana: boolean;
}

// Krona blob URLs are fetched manually rather than via TanStack Query because
// the per-URL revoke-on-unmount lifecycle is awkward when the URL list changes
// (one entry per classifier, or per sample for trana). Errors are surfaced
// inline; this is intentionally NOT a silent-failure path.
export default function CaseClassifierKrona({
  caseId,
  classifiers,
  samples,
  activeClassifier,
  isTrana,
}: Readonly<CaseClassifierKronaProps>) {
  const [kronaUrls, setKronaUrls] = useState<Record<string, string>>({});
  const [kronaErrors, setKronaErrors] = useState<Record<string, boolean>>({});
  const [kronaSelectedSample, setKronaSelectedSample] = useState<string | null>(null);

  useEffect(() => {
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
  }, [classifiers, samples, caseId, isTrana]);

  // Revoke blob URLs when the URL set changes or on unmount.
  useEffect(() => {
    return () => {
      Object.values(kronaUrls).forEach(URL.revokeObjectURL);
    };
  }, [kronaUrls]);

  const kronaIsLoading = !kronaUrls[activeClassifier.name] && !kronaErrors[activeClassifier.name];

  if (isTrana) {
    if (!kronaSelectedSample)
      return <p className="text-xs text-gray-400">No Krona data available for this case.</p>;
    const selectedSample = samples.find((s) => s._id === kronaSelectedSample);
    return (
      <>
        <div className="flex gap-1.5 mb-3">
          {samples
            .filter((s) => s.has_krona)
            .map((s) => (
              <button
                key={s._id as string}
                onClick={() => setKronaSelectedSample(s._id ?? null)}
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
            title={`Krona — ${selectedSample?.sample_id}`}
            className="w-full rounded-lg border border-gray-100"
            style={{ height: "75vh" }}
            sandbox="allow-scripts allow-popups allow-forms"
          />
        )}
      </>
    );
  }

  if (!activeClassifier.krona_id)
    return <p className="text-xs text-gray-400">No Krona data available for this case.</p>;
  return (
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
  );
}
