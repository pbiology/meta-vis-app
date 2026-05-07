import SampleDetailContent from "../../SampleDetailContent";

interface CaseSampleDetailProps {
  sampleId: string;
  // Human-readable sample identifier used as the report-selection key.
  // Defaults to `sampleId` for legacy callers that pass it directly.
  selectionKey?: string;
  onBack: () => void;
}

export default function CaseSampleDetail({
  sampleId,
  selectionKey,
  onBack,
}: Readonly<CaseSampleDetailProps>) {
  return <SampleDetailContent sampleId={sampleId} selectionKey={selectionKey} onBack={onBack} />;
}
