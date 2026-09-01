import { useEffect, useMemo, useRef, useState } from "react";
import {
  useAddCaseNote,
  useCase,
  useCaseSamples,
  useDeleteCaseNote,
  useReviewCase,
  useUnreviewCase,
  useUpdateCaseReport,
} from "../hooks/queries/useCases";
import { useOutbreaks, usePathogens } from "../hooks/queries/useAlerts";
import { useNtcContaminantCaseIds } from "../hooks/queries/useNtc";
import type { Case, CaseNote } from "../api/types";
import { flattenCaseDetail } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { useParams } from "react-router-dom";
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
  // /cases/:caseId/analyses/:version addresses one run; bare route = latest.
  const { version: versionParam } = useParams();
  const version = versionParam ? Number(versionParam) : null;
  const { role, user } = useAuth();

  const caseQ = useCase(caseId, version);
  const samplesQ = useCaseSamples(caseId, null, version);
  const pathogensQ = usePathogens();
  const outbreaksQ = useOutbreaks(14);
  const ntcCaseIdsQ = useNtcContaminantCaseIds();

  const reviewMutation = useReviewCase();
  const unreviewMutation = useUnreviewCase();
  const addNoteMutation = useAddCaseNote();
  const deleteNoteMutation = useDeleteCaseNote();
  const updateReportMutation = useUpdateCaseReport();

  const caseData = caseQ.data ?? null;
  const samples = useMemo(() => samplesQ.data ?? [], [samplesQ.data]);
  const pathogenMap = useMemo(
    () => Object.fromEntries((pathogensQ.data ?? []).map((p) => [p.taxon_id, p])),
    [pathogensQ.data]
  );

  const [section, setSection] = useState<CaseSection>("overview");
  const [activeSampleId, setActiveSampleId] = useState<string | null>(null);
  const [unreviewConfirm, setUnreviewConfirm] = useState(false);

  const { selectedFor, hydrate } = useReportBuilder();
  const reportCount = samples.reduce((n, s) => n + selectedFor(s.sample_id).length, 0);

  // Snapshot of this case's selections, used for the debounced server save.
  // Stable string lets the effect dedupe identical states.
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

  // The page shows a case *at* one analysis, so identity and run fields are
  // merged into a single object for the presentational components.
  const merged = caseData ? flattenCaseDetail(caseData) : null;
  const analyses = caseData?.analyses ?? [];
  const currentAnalysis = caseData?.analysis ?? null;
  const isSuperseded = currentAnalysis ? !currentAnalysis.is_latest : false;
  const review = currentAnalysis?.review as
    | { reviewed?: boolean; reviewed_by?: string }
    | undefined;
  const reviewed = review?.reviewed ?? false;
  const notes = (merged?.notes as CaseNote[] | undefined) ?? [];
  const classifiers = (currentAnalysis?.classifiers as Classifier[] | undefined) ?? [];
  const ticketId = merged?.ticket_id as string | undefined;
  const ticketUrl = merged?.ticket_url as string | undefined;
  const hasMultiqc = (currentAnalysis?.has_multiqc as boolean | undefined) ?? false;

  // Seed selections from the persisted server-side draft when the case loads.
  // Marking the snapshot as "already saved" prevents the post-hydration effect
  // from echoing it back to the server.
  useEffect(() => {
    if (!caseData) return;
    const persisted =
      (currentAnalysis as { report_selections?: Record<string, number[]> } | null)
        ?.report_selections ?? {};
    hydrate(persisted);
    const seed = Object.fromEntries(Object.entries(persisted).filter(([, ids]) => ids.length > 0));
    lastSavedRef.current = JSON.stringify(seed);
  }, [caseData, hydrate]);

  // Debounced persistence of the per-case selection snapshot. Skips writes
  // when the snapshot matches what we last sent (covers post-hydration echo
  // and selections that didn't actually change).
  useEffect(() => {
    if (!canEditReport) return;
    if (lastSavedRef.current === null) return; // case not loaded yet
    if (lastSavedRef.current === caseSelectionsSnapshot) return;
    const handle = setTimeout(() => {
      const payload = JSON.parse(caseSelectionsSnapshot) as Record<string, number[]>;
      updateReportMutation.mutate(
        { caseId, selections: payload, version },
        {
          onSuccess: () => {
            lastSavedRef.current = caseSelectionsSnapshot;
          },
          onError: (err) => {
            console.error("Failed to persist report selections", err);
          },
        }
      );
    }, 500);
    return () => clearTimeout(handle);
  }, [caseId, version, caseSelectionsSnapshot, canEditReport, updateReportMutation]);

  // Derived signal pills (pathogen / outbreak / ntc) computed from the
  // cross-cutting endpoints + the case's own samples.
  const signals = useMemo<SignalKind[]>(() => {
    const detected = new Set<SignalKind>();
    if (outbreaksQ.data?.outbreaks.some((o) => o.case_ids.includes(caseId))) {
      detected.add("outbreak");
    }
    if (ntcCaseIdsQ.data?.case_ids.includes(caseId)) {
      detected.add("ntc");
    }
    const hasPathogen = samples.some((s) => {
      const ids = (s.all_taxon_ids as number[] | undefined) ?? [];
      return ids.some((id) => id in pathogenMap);
    });
    if (hasPathogen) detected.add("pathogen");
    return Array.from(detected);
  }, [outbreaksQ.data, ntcCaseIdsQ.data, samples, pathogenMap, caseId]);

  async function handleReview() {
    try {
      await reviewMutation.mutateAsync({ caseId });
    } catch {
      alert("Failed to mark as reviewed.");
    }
  }

  async function handleUnreview() {
    setUnreviewConfirm(false);
    try {
      await unreviewMutation.mutateAsync({ caseId, version });
    } catch {
      alert("Failed to remove review.");
    }
  }

  async function handleAddNote(text: string) {
    await addNoteMutation.mutateAsync({ caseId, text });
  }

  async function handleDeleteNote(noteId: string) {
    await deleteNoteMutation.mutateAsync({ caseId, noteId });
  }

  const isLoading = caseQ.isLoading || samplesQ.isLoading;
  const isError = caseQ.isError || samplesQ.isError;

  if (isLoading)
    return (
      <div className="flex items-center justify-center h-screen text-sm text-gray-400">
        Loading…
      </div>
    );
  if (isError || !caseData || !merged)
    return (
      <div className="flex items-center justify-center h-screen text-sm text-red-500">
        Failed to load case.
      </div>
    );

  const reviewing = reviewMutation.isPending || unreviewMutation.isPending;

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
        analyses={analyses}
        currentVersion={currentAnalysis?.version ?? null}
        isSuperseded={isSuperseded}
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
              caseData={merged as Case}
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
          {section === "report" && (
            <CaseReportSection
              caseId={caseId}
              samples={samples}
              version={version}
              analyses={analyses}
              canEdit={canEditReport}
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
          {section === "provenance" && <CaseProvenance caseData={merged as Case} />}
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
