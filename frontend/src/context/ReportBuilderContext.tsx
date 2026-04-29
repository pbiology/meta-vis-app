import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  ReactNode,
} from "react";

// Tracks taxa the user has marked for inclusion in the printable report.
// State is keyed by sample_id so a draft survives navigation between
// SampleDetail and TaxonDetail without leaking selections across samples.

const STORAGE_KEY = "report-builder";

type Selections = Record<string, number[]>;

interface ReportBuilderContextValue {
  selectedFor: (sampleId: string) => number[];
  isSelected: (sampleId: string, taxonId: number) => boolean;
  addTaxon: (sampleId: string, taxonId: number) => void;
  removeTaxon: (sampleId: string, taxonId: number) => void;
  clear: (sampleId: string) => void;
}

const ReportBuilderContext = createContext<ReportBuilderContextValue | null>(null);

function loadFromSession(): Selections {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return {};
    const out: Selections = {};
    for (const [sampleId, taxonIds] of Object.entries(parsed as Record<string, unknown>)) {
      if (Array.isArray(taxonIds)) {
        out[sampleId] = taxonIds.filter((v): v is number => typeof v === "number");
      }
    }
    return out;
  } catch {
    return {};
  }
}

function saveToSession(selections: Selections) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(selections));
  } catch {
    // sessionStorage unavailable (private mode, quota) — silently skip.
  }
}

export function ReportBuilderProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [selections, setSelections] = useState<Selections>(() => loadFromSession());

  useEffect(() => {
    saveToSession(selections);
  }, [selections]);

  const selectedFor = useCallback(
    (sampleId: string): number[] => selections[sampleId] ?? [],
    [selections]
  );

  const isSelected = useCallback(
    (sampleId: string, taxonId: number): boolean => (selections[sampleId] ?? []).includes(taxonId),
    [selections]
  );

  const addTaxon = useCallback((sampleId: string, taxonId: number) => {
    setSelections((prev) => {
      const current = prev[sampleId] ?? [];
      if (current.includes(taxonId)) return prev;
      return { ...prev, [sampleId]: [...current, taxonId] };
    });
  }, []);

  const removeTaxon = useCallback((sampleId: string, taxonId: number) => {
    setSelections((prev) => {
      const current = prev[sampleId];
      if (!current?.includes(taxonId)) return prev;
      const next = current.filter((id) => id !== taxonId);
      if (next.length === 0) {
        // Drop empty entries so sessionStorage doesn't accumulate stale sample keys.
        const copy = { ...prev };
        delete copy[sampleId];
        return copy;
      }
      return { ...prev, [sampleId]: next };
    });
  }, []);

  const clear = useCallback((sampleId: string) => {
    setSelections((prev) => {
      if (!(sampleId in prev)) return prev;
      const copy = { ...prev };
      delete copy[sampleId];
      return copy;
    });
  }, []);

  const value = useMemo(
    () => ({ selectedFor, isSelected, addTaxon, removeTaxon, clear }),
    [selectedFor, isSelected, addTaxon, removeTaxon, clear]
  );

  return <ReportBuilderContext.Provider value={value}>{children}</ReportBuilderContext.Provider>;
}

export function useReportBuilder(): ReportBuilderContextValue {
  const ctx = useContext(ReportBuilderContext);
  if (!ctx) throw new Error("useReportBuilder must be used inside ReportBuilderProvider");
  return ctx;
}
