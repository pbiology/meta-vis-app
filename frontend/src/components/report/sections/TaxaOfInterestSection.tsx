import type { ReportTaxon } from "../useReportData";
import SectionHeading from "./SectionHeading";

function formatPct(value: number | undefined): string {
  if (value == null) return "—";
  if (value < 0.001) return "<0.001%";
  return `${value.toFixed(3)}%`;
}

interface TaxaOfInterestSectionProps {
  taxa: ReportTaxon[];
}

export default function TaxaOfInterestSection({ taxa }: Readonly<TaxaOfInterestSectionProps>) {
  return (
    <section className="report-section">
      <SectionHeading number={3} title="Taxa of interest" />
      {taxa.length === 0 ? (
        <p className="report-soft">No taxa selected.</p>
      ) : (
        <ul className="report-taxa-list">
          {taxa.map((t) => {
            const classifiers = Object.keys(t.abundance).sort((a, b) => a.localeCompare(b));
            return (
              <li
                key={t.taxon_id}
                className={`report-taxon${t.pathogen ? " report-taxon-pathogen" : ""}`}
              >
                <div className="report-taxon-header">
                  <span className="report-taxon-name">{t.name}</span>
                  <span className="report-taxon-meta">
                    {[t.rank, t.superkingdom].filter(Boolean).join(" · ")}
                  </span>
                </div>
                {classifiers.length > 0 && (
                  <table className="report-taxon-grid">
                    <thead>
                      <tr>
                        <th />
                        {classifiers.map((c) => (
                          <th key={c}>{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td className="report-taxon-grid-label">Reads</td>
                        {classifiers.map((c) => (
                          <td key={c} className="report-mono">
                            {t.abundance[c]?.toLocaleString() ?? "0"}
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td className="report-taxon-grid-label">% non-host</td>
                        {classifiers.map((c) => (
                          <td key={c} className="report-mono">
                            {formatPct(t.pct[c])}
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
