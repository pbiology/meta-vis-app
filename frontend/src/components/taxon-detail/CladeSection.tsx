import { useState, type ReactNode } from "react";
import { useSampleClade, useSampleProfile } from "../../hooks/queries/useSamples";
import { axiosErrorDetail, axiosErrorStatus } from "../../utils/axiosError";
import CladeTree from "./CladeTree";
import CladeUnplacedNotice from "./CladeUnplacedNotice";
import type { CladeResponse } from "../../api/types";

interface CladeSectionProps {
  // Mongo _id of the sample the taxon was opened from.
  sampleOid: string;
  taxonId: number;
  // The classifier tab active in the taxonomy table, when known.
  initialClassifier?: string;
}

/**
 * Related taxa in this sample and the negative controls declared for it.
 *
 * Matching on exact taxon ID misses the same organism classified as a sibling
 * strain or species, or left at a higher rank. This lays the whole genus out
 * side by side so the reviewer can judge it; it deliberately draws no
 * conclusion itself.
 */
export default function CladeSection({
  sampleOid,
  taxonId,
  initialClassifier,
}: Readonly<CladeSectionProps>) {
  const profileQ = useSampleProfile(sampleOid);
  const classifiers = (profileQ.data?.profiles ?? []).map((p) => p.classifier);
  const [chosen, setChosen] = useState<string | null>(null);
  const active = pickClassifier(classifiers, chosen, initialClassifier);
  const cladeQ = useSampleClade(sampleOid, active, taxonId);

  return (
    <section className="bg-white border border-gray-100 rounded-xl">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
        <p className="text-xs font-medium text-gray-400 uppercase tracking-wider flex-1">
          Related taxa in sample and controls
        </p>
        {classifiers.length > 1 && (
          <div className="flex gap-1">
            {classifiers.map((clf) => (
              <button
                key={clf}
                type="button"
                onClick={() => setChosen(clf)}
                aria-pressed={active === clf}
                className={`text-xs px-2.5 py-1 rounded-full transition-colors ${
                  active === clf
                    ? "bg-gray-900 text-white"
                    : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                }`}
              >
                {clf}
              </button>
            ))}
          </div>
        )}
      </div>
      <SectionBody
        profileLoading={profileQ.isLoading}
        profileFailed={profileQ.isError}
        hasClassifiers={classifiers.length > 0}
        cladeLoading={cladeQ.isLoading}
        cladeError={cladeQ.error}
        data={cladeQ.data}
      />
    </section>
  );
}

interface SectionBodyProps {
  profileLoading: boolean;
  profileFailed: boolean;
  hasClassifiers: boolean;
  cladeLoading: boolean;
  cladeError: unknown;
  data: CladeResponse | undefined;
}

function SectionBody({
  profileLoading,
  profileFailed,
  hasClassifiers,
  cladeLoading,
  cladeError,
  data,
}: Readonly<SectionBodyProps>) {
  if (profileLoading || cladeLoading) {
    return <div className="px-4 py-8 text-xs text-gray-400 text-center">Loading…</div>;
  }
  if (profileFailed) {
    return <Message tone="error">Failed to load the sample&apos;s classifier profiles.</Message>;
  }
  if (!hasClassifiers) {
    return <Message tone="muted">This sample has no classifier profiles.</Message>;
  }
  if (cladeError) {
    // 409: the taxonomy reference must be reloaded; the detail says how.
    const tone = axiosErrorStatus(cladeError) === 409 ? "warning" : "error";
    return (
      <Message tone={tone}>{axiosErrorDetail(cladeError, "Failed to load related taxa.")}</Message>
    );
  }
  if (!data) return null;

  const openedAtGenus = data.anchor.taxon_id !== data.clicked.taxon_id;
  return (
    <>
      <div className="px-4 py-2.5 border-b border-gray-50 text-xs text-gray-500">
        All taxa under <span className="italic font-medium text-gray-700">{data.anchor.name}</span>
        {data.anchor.rank && ` (${data.anchor.rank})`} with signal in this sample or its negative
        controls
        {openedAtGenus && (
          <>
            , opened at the genus of{" "}
            <span className="italic text-gray-700">{data.clicked.name}</span>
          </>
        )}
        .
        <p className="mt-1 text-[11px] text-gray-400">
          {data.unit === "reads"
            ? `Each value is reads for the taxon and everything below it, with reads per million of all reads ${data.classifier} processed for that sample. "direct" is reads assigned to the taxon itself.`
            : `Each value is relative abundance for the taxon and everything below it. "direct" is abundance assigned to the taxon itself.`}
        </p>
      </div>
      <CladeUnplacedNotice unplaced={data.unplaced} columns={data.columns} unit={data.unit} />
      <CladeTree
        key={`${data.classifier}-${data.anchor.taxon_id}-${data.clicked.taxon_id}`}
        data={data}
      />
    </>
  );
}

function pickClassifier(
  available: string[],
  chosen: string | null,
  initial: string | undefined
): string | null {
  if (chosen && available.includes(chosen)) return chosen;
  if (initial && available.includes(initial)) return initial;
  return available[0] ?? null;
}

const TONE_CLASS = {
  muted: "text-gray-300",
  warning: "text-amber-700 bg-amber-50",
  error: "text-red-600",
} as const;

function Message({
  tone,
  children,
}: Readonly<{ tone: keyof typeof TONE_CLASS; children: ReactNode }>) {
  return <div className={`px-4 py-6 text-xs text-center ${TONE_CLASS[tone]}`}>{children}</div>;
}
