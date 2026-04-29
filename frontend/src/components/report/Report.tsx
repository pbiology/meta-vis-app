import type { ReportData } from "./useReportData";
import SampleInfoSection from "./sections/SampleInfoSection";
import SubjectSection from "./sections/SubjectSection";
import TaxaOfInterestSection from "./sections/TaxaOfInterestSection";
import CommentsSection from "./sections/CommentsSection";
import ProvenanceSection from "./sections/ProvenanceSection";

interface ReportProps {
  data: ReportData;
}

// The printable artifact. .report-root + the print CSS in index.css ensures only
// this subtree is visible when the user prints.
export default function Report({ data }: Readonly<ReportProps>) {
  return (
    <div className="report-root">
      <div className="report-page">
        <header className="report-header">
          <h1 className="report-title">Sample report</h1>
          <p className="report-subtitle">
            <span className="report-mono">{data.sample.sample_id}</span>
          </p>
        </header>
        <SampleInfoSection sample={data.sample} />
        <SubjectSection subject={data.subject} />
        <TaxaOfInterestSection taxa={data.taxa} />
        <CommentsSection caseNotes={data.notes} sampleNote={data.sampleNote} />
      </div>
      <ProvenanceSection pipelineInfo={data.pipelineInfo} generatedAt={data.generatedAt} />
    </div>
  );
}
