import type { ReportSampleRow } from "../useReportData";
import SectionHeading from "./SectionHeading";

interface SamplesListSectionProps {
  samples: ReportSampleRow[];
}

const DASH = "—";

function fmtNum(n: number | undefined): string {
  return typeof n === "number" ? n.toLocaleString("en-US") : DASH;
}

function fmtPct(rate: number | undefined): string {
  return typeof rate === "number" ? `${(rate * 100).toFixed(2)}%` : DASH;
}

// Compact case-level samples table: one row per sample, the columns the
// reviewer needs at a glance (id, material, source, passed-filter reads, Q30).
export default function SamplesListSection({ samples }: Readonly<SamplesListSectionProps>) {
  return (
    <section className="report-section">
      <SectionHeading number={3} title="Samples" />
      {samples.length === 0 ? (
        <p className="report-soft">No samples in this case.</p>
      ) : (
        <table className="report-samples-table">
          <thead>
            <tr>
              <th>Sample</th>
              <th>Material</th>
              <th>Source</th>
              <th className="report-samples-table-num">Passed filter</th>
              <th className="report-samples-table-num">Q30</th>
            </tr>
          </thead>
          <tbody>
            {samples.map((s) => (
              <tr key={s.sample_id}>
                <td className="report-mono">{s.sample_id}</td>
                <td>{s.material ?? DASH}</td>
                <td>{s.sample_source ?? DASH}</td>
                <td className="report-mono report-samples-table-num">
                  {fmtNum(s.fastp?.passed_filter_reads)}
                </td>
                <td className="report-mono report-samples-table-num">
                  {fmtPct(s.fastp?.q30_rate)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
