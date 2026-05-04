import { useEffect, useMemo, useState } from "react";
import {
  addNote,
  deleteNote,
  getCase,
  getCaseSamples,
  reviewCase,
  unreviewCase,
} from "../api/cases";
import { getPathogens } from "../api/alerts";
import { getOutbreaks } from "../api/alerts";
import { getNtcContaminantCaseIds } from "../api/ntc";
import type { Case, CaseNote, PathogenItem, Sample } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { useRequiredParam } from "../utils/routeParams";
import CaseTopBar from "../components/case-view/CaseTopBar";
import CaseSidebar, { type CaseSection } from "../components/case-view/CaseSidebar";
import CaseOverview from "../components/case-view/sections/CaseOverview";
import CaseSamplesPanel from "../components/case-view/sections/CaseSamplesPanel";
import CaseClassifiers, { type Classifier } from "../components/case-view/sections/CaseClassifiers";
import CaseProvenance from "../components/case-view/sections/CaseProvenance";
import CaseComments from "../components/case-view/sections/CaseComments";
import CaseTaxa from "../components/case-view/sections/CaseTaxa";
import CaseMultiQC from "../components/case-view/sections/CaseMultiQC";
import type { SignalKind } from "../components/SignalPill";

function Placeholder({ title, body }: { title: string; body: string }) {
  return (
    <section className="bg-white border border-gray-100 rounded-lg p-10 text-center">
      <div className="text-sm font-semibold text-gray-700 mb-1">{title}</div>
      <div className="text-xs text-gray-400">{body}</div>
    </section>
  );
}

export default function CaseView() {
  const caseId = useRequiredParam("caseId");
  const { role, user } = useAuth();

  const [caseData, setCaseData] = useState<Case | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [pathogenMap, setPathogenMap] = useState<Record<number, PathogenItem>>({});
  const [signals, setSignals] = useState<SignalKind[]>([]);
  const [section, setSection] = useState<CaseSection>("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [unreviewConfirm, setUnreviewConfirm] = useState(false);

  useEffect(() => {
    document.title = `${caseId} — meta-vis`;
  }, [caseId]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [fetchedCase, samplesData, pathogens] = await Promise.all([
          getCase(caseId),
          getCaseSamples(caseId),
          getPathogens(),
        ]);
        if (cancelled) return;
        setCaseData(fetchedCase);
        setSamples(samplesData);
        setPathogenMap(Object.fromEntries(pathogens.map((p) => [p.taxon_id, p])));
      } catch {
        if (!cancelled) setError("Failed to load case.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  // Derive signal pills (pathogen / outbreak / ntc) from cross-cutting endpoints.
  useEffect(() => {
    let cancelled = false;
    async function loadSignals() {
      const detected: SignalKind[] = [];
      try {
        const outbreaks = await getOutbreaks(14);
        if (outbreaks.outbreaks.some((o) => o.case_ids.includes(caseId))) {
          detected.push("outbreak");
        }
      } catch {
        /* noop */
      }
      try {
        const ntc = await getNtcContaminantCaseIds();
        if (ntc.case_ids.includes(caseId)) detected.push("ntc");
      } catch {
        /* noop */
      }
      // Pathogen presence is derivable from samples + pathogenMap once loaded;
      // resolved below in a separate effect when those are populated.
      if (!cancelled) setSignals((prev) => Array.from(new Set([...prev, ...detected])));
    }
    loadSignals();
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  useEffect(() => {
    const hasPathogen = samples.some((s) => {
      const ids = (s.all_taxon_ids as number[] | undefined) ?? [];
      return ids.some((id) => id in pathogenMap);
    });
    setSignals((prev) => {
      const next = new Set(prev);
      if (hasPathogen) next.add("pathogen");
      else next.delete("pathogen");
      return Array.from(next);
    });
  }, [samples, pathogenMap]);

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

  async function handleAddNote(text: string) {
    const note = await addNote(caseId, text);
    setCaseData((prev) => {
      if (!prev) return prev;
      const prevNotes = (prev.notes as CaseNote[] | undefined) ?? [];
      return { ...prev, notes: [...prevNotes, note as unknown as CaseNote] } as Case;
    });
  }

  async function handleDeleteNote(noteId: string) {
    await deleteNote(caseId, noteId);
    setCaseData((prev) => {
      if (!prev) return prev;
      const prevNotes = (prev.notes as CaseNote[] | undefined) ?? [];
      return { ...prev, notes: prevNotes.filter((n) => n.id !== noteId) } as Case;
    });
  }

  const review = caseData?.review as { reviewed?: boolean; reviewed_by?: string } | undefined;
  const reviewed = review?.reviewed ?? false;
  const notes = (caseData?.notes as CaseNote[] | undefined) ?? [];
  const classifiers = (caseData?.classifiers as Classifier[] | undefined) ?? [];
  const ticketId = caseData?.ticket_id as string | undefined;
  const ticketUrl = caseData?.ticket_url as string | undefined;
  const hasMultiqc = (caseData?.has_multiqc as boolean | undefined) ?? false;

  const taxaCount = useMemo(() => {
    const ids = new Set<number>();
    for (const s of samples) {
      const taxa = (s.all_taxon_ids as number[] | undefined) ?? [];
      for (const id of taxa) if (id in pathogenMap) ids.add(id);
    }
    return ids.size;
  }, [samples, pathogenMap]);

  if (loading)
    return (
      <div className="flex items-center justify-center h-screen text-sm text-gray-400">
        Loading…
      </div>
    );
  if (error || !caseData)
    return (
      <div className="flex items-center justify-center h-screen text-sm text-red-500">
        {error ?? "Case not found."}
      </div>
    );

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <CaseTopBar
        caseId={caseId}
        signals={signals}
        reviewed={reviewed}
        reviewer={review?.reviewed_by ?? null}
        ticketId={ticketId}
        ticketUrl={ticketUrl}
        onReview={handleReview}
        onUnreviewRequest={() => setUnreviewConfirm(true)}
        reviewing={reviewing}
        canReview={role !== "reader"}
      />
      <div className="flex-1 flex min-h-0">
        <CaseSidebar
          active={section}
          onSelect={setSection}
          counts={{
            samples: samples.length,
            taxa: taxaCount,
            comments: notes.length,
          }}
          hideMultiqc={!hasMultiqc}
        />
        <main className="flex-1 overflow-y-auto px-8 py-6 min-w-0">
          {section === "overview" && (
            <CaseOverview
              caseId={caseId}
              caseData={caseData}
              samples={samples}
              notes={notes}
              signals={signals}
              onJumpToSamples={() => setSection("samples")}
              onJumpToComments={() => setSection("comments")}
            />
          )}
          {section === "samples" && (
            <>
              <CaseSamplesPanel samples={samples} pathogenMap={pathogenMap} />
              <CaseClassifiers
                caseId={caseId}
                classifiers={classifiers}
                samples={samples}
                showKrona
              />
            </>
          )}
          {section === "taxa" && <CaseTaxa samples={samples} pathogenMap={pathogenMap} />}
          {section === "multiqc" && <CaseMultiQC caseId={caseId} available={hasMultiqc} />}
          {section === "report" && (
            <Placeholder
              title="Report builder"
              body="Open a sample to select taxa for the printable report — selections persist across the case's samples."
            />
          )}
          {section === "comments" && (
            <CaseComments
              notes={notes}
              currentUser={user}
              role={role}
              onAdd={handleAddNote}
              onDelete={handleDeleteNote}
            />
          )}
          {section === "provenance" && <CaseProvenance caseData={caseData} />}
        </main>
      </div>

      {unreviewConfirm && reviewed && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl border border-gray-100 shadow-lg p-6 w-80 flex flex-col gap-4">
            <p className="text-sm font-medium text-gray-900 m-0">Remove review?</p>
            <p className="text-xs text-gray-500 m-0">
              This will remove the review by{" "}
              <span className="font-medium">{review?.reviewed_by ?? "—"}</span> and reset the case
              to pending.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setUnreviewConfirm(false)}
                className="px-3 py-1.5 text-xs rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleUnreview}
                className="px-3 py-1.5 text-xs rounded-md bg-gray-900 text-white hover:bg-gray-800"
              >
                Remove review
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
