import { useEffect, useRef, useState } from "react";
import {
  addNote,
  deleteNote,
  getCase,
  getCaseSamples,
  reviewCase,
  unreviewCase,
  updateCaseReport,
} from "../api/cases";
import { getOutbreaks, getPathogens } from "../api/alerts";
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
import CaseMultiQC from "../components/case-view/sections/CaseMultiQC";
import CaseSampleDetail from "../components/case-view/sections/CaseSampleDetail";
import CaseReportSection from "../components/case-view/sections/CaseReportSection";
import type { SignalKind } from "../components/SignalPill";
import { useReportBuilder } from "../context/ReportBuilderContext";

export default function CaseView() {
  const caseId = useRequiredParam("caseId");
  const { role, user } = useAuth();

  const [caseData, setCaseData] = useState<Case | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [pathogenMap, setPathogenMap] = useState<Record<number, PathogenItem>>({});
  const [signals, setSignals] = useState<SignalKind[]>([]);
  const [section, setSection] = useState<CaseSection>("overview");
  const [activeSampleId, setActiveSampleId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [unreviewConfirm, setUnreviewConfirm] = useState(false);

  const { selectedFor, hydrate } = useReportBuilder();
  const reportCount = samples.reduce((n, s) => n + selectedFor(s.sample_id).length, 0);

  // Snapshot of this case's selections, used for the debounced server save.
  // Stable string lets useEffect dedupe identical states.
  const caseSelectionsSnapshot = JSON.stringify(
    Object.fromEntries(
      samples
        .map((s) => [s.sample_id, selectedFor(s.sample_id)] as const)
        .filter(([, ids]) => ids.length > 0)
    )
  );
  const lastSavedRef = useRef<string | null>(null);
  const canEditReport = role !== "reader";

  useEffect(() => {
    document.title = `${caseId} — meta-vis`;
  }, [caseId]);

  function handleSectionChange(s: CaseSection) {
    setSection(s);
    setActiveSampleId(null);
  }

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
        // Seed selections from the persisted server-side draft. Mark this state
        // as "already saved" so the post-hydration effect doesn't echo it back.
        const persisted =
          (fetchedCase as { report_selections?: Record<string, number[]> }).report_selections ?? {};
        hydrate(persisted);
        const seed = Object.fromEntries(
          Object.entries(persisted).filter(([, ids]) => ids.length > 0)
        );
        lastSavedRef.current = JSON.stringify(seed);
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
  }, [caseId, hydrate]);

  // Debounced persistence of the per-case selection snapshot. Skips writes
  // when the snapshot matches what we last sent (covers post-hydration echo
  // and selections that didn't actually change).
  useEffect(() => {
    if (!canEditReport) return;
    if (lastSavedRef.current === null) return; // case not loaded yet
    if (lastSavedRef.current === caseSelectionsSnapshot) return;
    const handle = setTimeout(() => {
      const payload = JSON.parse(caseSelectionsSnapshot) as Record<string, number[]>;
      updateCaseReport(caseId, payload)
        .then(() => {
          lastSavedRef.current = caseSelectionsSnapshot;
        })
        .catch((err) => {
          console.error("Failed to persist report selections", err);
        });
    }, 500);
    return () => clearTimeout(handle);
  }, [caseId, caseSelectionsSnapshot, canEditReport]);

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
        reportCount={reportCount}
        onOpenReport={() => handleSectionChange("report")}
      />
      <div className="flex-1 flex min-h-0">
        <CaseSidebar
          active={section}
          onSelect={handleSectionChange}
          counts={{
            samples: samples.length,
            comments: notes.length,
          }}
          hideMultiqc={!hasMultiqc}
        />
        <main className="flex-1 overflow-y-auto px-8 py-6 min-w-0">
          {section === "overview" && (
            <CaseOverview
              caseData={caseData}
              samples={samples}
              notes={notes}
              signals={signals}
              pathogenMap={pathogenMap}
              onJumpToComments={() => handleSectionChange("comments")}
              onSelectSample={(id) => {
                setSection("samples");
                setActiveSampleId(id);
              }}
            />
          )}
          {section === "samples" && activeSampleId && (
            <CaseSampleDetail
              sampleId={activeSampleId}
              selectionKey={samples.find((s) => (s._id as string) === activeSampleId)?.sample_id}
              onBack={() => setActiveSampleId(null)}
            />
          )}
          {section === "samples" && !activeSampleId && (
            <>
              <CaseSamplesPanel
                samples={samples}
                pathogenMap={pathogenMap}
                onSelectSample={setActiveSampleId}
              />
              <CaseClassifiers
                caseId={caseId}
                classifiers={classifiers}
                samples={samples}
                showKrona
                onSelectSample={setActiveSampleId}
              />
            </>
          )}
          {section === "multiqc" && <CaseMultiQC caseId={caseId} available={hasMultiqc} />}
          {section === "report" && <CaseReportSection caseId={caseId} samples={samples} />}
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
