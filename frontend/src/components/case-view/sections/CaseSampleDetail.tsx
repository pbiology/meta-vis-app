import SampleDetailContent from "../../SampleDetailContent";

interface CaseSampleDetailProps {
  sampleId: string;
  onBack: () => void;
}

export default function CaseSampleDetail({ sampleId, onBack }: Readonly<CaseSampleDetailProps>) {
  return <SampleDetailContent sampleId={sampleId} onBack={onBack} />;
}
