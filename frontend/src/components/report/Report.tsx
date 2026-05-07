import type { ReportData } from "./useReportData";
import OverviewSection from "./sections/OverviewSection";
import SamplesListSection from "./sections/SamplesListSection";
import SubjectsSection from "./sections/SubjectsSection";
import TaxaOfInterestSection from "./sections/TaxaOfInterestSection";
import CommentsSection from "./sections/CommentsSection";
import ProvenanceSection from "./sections/ProvenanceSection";

interface ReportProps {
  data: ReportData;
}

// Case-scoped printable report. .report-root + the print CSS in index.css
// ensures only this subtree is visible when the user prints.
export default function Report({ data }: Readonly<ReportProps>) {
  return (
    <div className="report-root">
      <div className="report-page">
        <header className="report-header">
          <h1 className="report-title">Case report</h1>
          <p className="report-subtitle">
            <span className="report-mono">{data.caseDoc.case_id}</span>
          </p>
        </header>
        <OverviewSection
          caseDoc={data.caseDoc}
          sampleCount={data.samples.length}
          generatedAt={data.generatedAt}
        />
        <SubjectsSection subjects={data.subjects} />
        <SamplesListSection samples={data.samples} />
        <CommentsSection caseNotes={data.notes} sampleNote={null} />
        <TaxaOfInterestSection
          taxa={data.taxa}
          samples={data.samples}
          classifiers={data.classifiers}
        />
      </div>
      <ProvenanceSection taxprofilerInfo={data.taxprofilerInfo} metavalInfo={data.metavalInfo} />
    </div>
  );
}
