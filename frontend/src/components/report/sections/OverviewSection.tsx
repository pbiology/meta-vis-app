import type { CaseListItem } from "../../../api/types";
import KeyValueGrid, { type KvPair } from "./KeyValueGrid";
import SectionHeading from "./SectionHeading";

interface OverviewSectionProps {
  caseDoc: CaseListItem;
  sampleCount: number;
}

function readString(doc: CaseListItem, key: string): string | undefined {
  const v = (doc as Record<string, unknown>)[key];
  return typeof v === "string" ? v : undefined;
}

// Case-level overview at the top of the report. Mirrors the per-sample
// "Sample information" overview the report previously opened with, but
// scoped to the case identity + run-level metadata that's shared across
// every sample in the case.
export default function OverviewSection({ caseDoc, sampleCount }: Readonly<OverviewSectionProps>) {
  const pairs: KvPair[] = [
    { label: "Case ID", value: caseDoc.case_id, mono: true },
    { label: "Ticket", value: caseDoc.ticket_id ?? undefined, mono: true },
    { label: "Order date", value: caseDoc.order_date ?? undefined },
    { label: "Sequencing platform", value: readString(caseDoc, "sequencing_platform") },
    { label: "Analysis type", value: caseDoc.analysis_type },
    { label: "Samples", value: sampleCount, mono: true },
  ];

  return (
    <section className="report-section">
      <SectionHeading number={1} title="Overview" />
      <KeyValueGrid pairs={pairs} />
    </section>
  );
}
