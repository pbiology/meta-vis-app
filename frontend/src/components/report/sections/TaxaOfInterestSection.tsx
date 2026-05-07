import type { ReportSampleRow, ReportTaxon } from "../useReportData";
import SectionHeading from "./SectionHeading";

const DASH = "—";

function fmtReads(value: number | undefined): string {
  return typeof value === "number" ? value.toLocaleString("en-US") : DASH;
}

function fmtPct(value: number | undefined): string {
  if (typeof value !== "number") return DASH;
  if (value === 0) return "0%";
  if (value < 0.001) return "<0.001%";
  return `${value.toFixed(3)}%`;
}

interface TaxonReadsMatrixProps {
  taxon: ReportTaxon;
  samples: ReportSampleRow[];
  classifiers: string[];
}

// Per-taxon (sample × classifier) matrix. Sample rows in canonical order
// (DNA before RNA, see utils/sampleOrdering); classifier columns in
// alphabetical order; both fixed at the report level so cards line up.
function TaxonReadsMatrix({ taxon, samples, classifiers }: Readonly<TaxonReadsMatrixProps>) {
  if (samples.length === 0 || classifiers.length === 0) return null;
  return (
    <table className="report-taxon-matrix">
      <thead>
        <tr>
          <th />
          {classifiers.map((c) => (
            <th key={c} className="report-taxon-matrix-col">
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {samples.map((s) => {
          const row = taxon.cells[s.sample_id];
          return (
            <tr key={s.sample_id}>
              <td className="report-taxon-matrix-rowlabel">
                <span className="report-taxon-matrix-rowlabel-id">{s.sample_id}</span>
                {s.sample_type === "negative_ctrl" && (
                  <span className="report-taxon-matrix-rowlabel-ntc">negative control</span>
                )}
              </td>
              {classifiers.map((c) => {
                const cell = row?.[c];
                return (
                  <td key={c} className="report-taxon-matrix-cell">
                    <div className="report-mono report-taxon-matrix-cell-reads">
                      {fmtReads(cell?.reads)}
                    </div>
                    <div className="report-mono report-taxon-matrix-cell-pct">
                      {fmtPct(cell?.pct)}
                    </div>
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

interface TaxaOfInterestSectionProps {
  taxa: ReportTaxon[];
  samples: ReportSampleRow[];
  classifiers: string[];
}

export default function TaxaOfInterestSection({
  taxa,
  samples,
  classifiers,
}: Readonly<TaxaOfInterestSectionProps>) {
  return (
    <section className="report-section">
      <SectionHeading number={4} title="Taxa of interest" />
      {taxa.length === 0 ? (
        <p className="report-soft">No taxa selected.</p>
      ) : (
        <ul className="report-taxa-list">
          {taxa.map((t) => (
            <li
              key={t.taxon_id}
              className={`report-taxon${t.pathogen ? " report-taxon-pathogen" : ""}`}
            >
              <div className="report-taxon-header">
                <div className="report-taxon-header-left">
                  <span className="report-taxon-name">{t.name}</span>
                  <span className="report-mono report-taxon-taxid">taxid:{t.taxon_id}</span>
                </div>
                <span className="report-taxon-meta">
                  {[t.rank, t.superkingdom].filter(Boolean).join(" · ")}
                </span>
              </div>
              <TaxonReadsMatrix taxon={t} samples={samples} classifiers={classifiers} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
