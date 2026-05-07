import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import Report from "./Report";
import type { ReportData } from "./useReportData";

function makeData(overrides: Partial<ReportData> = {}): ReportData {
  return {
    generatedAt: "2026-04-29T10:00:00Z",
    caseDoc: {
      case_id: "lovelypanther",
      sample_count: 2,
      notes: [{ id: "n1", author: "alice", created_at: "2026-04-28", text: "Looks suspicious" }],
    },
    samples: [
      {
        sample_id: "S001-DNA",
        sample_type: "DNA",
        material: "DNA",
        classifiersAvailable: ["bracken", "kraken2"],
        fastp: {
          total_reads_before_filtering: 1000000,
          passed_filter_reads: 950000,
          q20_rate: 0.97,
          q30_rate: 0.93,
        },
      },
      {
        sample_id: "S001-RNA",
        sample_type: "RNA",
        material: "RNA",
        classifiersAvailable: ["kraken2"],
      },
    ],
    classifiers: ["bracken", "kraken2"],
    subjects: [{ sample_id: "S001-DNA", subject: { subject_id: "SUB-1", sex: "F" } }],
    notes: [{ id: "n1", author: "alice", created_at: "2026-04-28", text: "Looks suspicious" }],
    taxa: [
      {
        taxon_id: 11676,
        name: "HIV-1",
        rank: "species",
        superkingdom: "Viruses",
        pathogen: true,
        cells: {
          "S001-DNA": {
            kraken2: { reads: 1234, pct: 0.123 },
            bracken: { reads: 1100, pct: 0.11 },
          },
        },
      },
      {
        taxon_id: 562,
        name: "Escherichia coli",
        rank: "species",
        superkingdom: "Bacteria",
        pathogen: false,
        cells: {
          "S001-DNA": { kraken2: { reads: 50, pct: 0.005 } },
        },
      },
    ],
    taxprofilerInfo: {
      pipeline_name: "nf-core/taxprofiler",
      pipeline_version: "1.2.3",
      nextflow: "23.10.0",
    },
    metavalInfo: undefined,
    ...overrides,
  };
}

describe("Report", () => {
  it("renders the case-scoped header", () => {
    render(<Report data={makeData()} />);
    expect(screen.getByRole("heading", { name: "Case report" })).toBeInTheDocument();
    // case_id appears in both the header subtitle and the Overview section.
    expect(screen.getAllByText("lovelypanther").length).toBeGreaterThan(0);
  });

  it("renders all six body sections", () => {
    render(<Report data={makeData()} />);
    for (const title of ["Overview", "Subject", "Taxa of interest", "Comments", "Provenance"]) {
      expect(screen.getByRole("heading", { level: 2, name: title })).toBeInTheDocument();
    }
    // "Samples" also appears as a table column header, so match the section heading.
    expect(screen.getByRole("heading", { level: 2, name: "Samples" })).toBeInTheDocument();
  });

  it("shows the taxon id in each taxon header", () => {
    render(<Report data={makeData()} />);
    expect(screen.getByText("taxid:11676")).toBeInTheDocument();
    expect(screen.getByText("taxid:562")).toBeInTheDocument();
  });

  it("flags pathogen taxa with the pathogen modifier class", () => {
    render(<Report data={makeData()} />);
    const hivItem = screen.getByText("HIV-1").closest("li")!;
    const ecoliItem = screen.getByText("Escherichia coli").closest("li")!;
    expect(hivItem.className).toContain("report-taxon-pathogen");
    expect(ecoliItem.className).not.toContain("report-taxon-pathogen");
  });

  it("renders 'Not linked' when no subject is linked to any sample", () => {
    render(<Report data={makeData({ subjects: [{ sample_id: "S001-DNA", subject: null }] })} />);
    expect(screen.getByText("Not linked")).toBeInTheDocument();
  });

  it("wraps the provenance section in .report-page-break", () => {
    const { container } = render(<Report data={makeData()} />);
    const wrapper = container.querySelector(".report-page-break");
    expect(wrapper).not.toBeNull();
    expect(within(wrapper as HTMLElement).getByText("Provenance")).toBeInTheDocument();
  });

  it("renders em-dash for missing per-sample fields", () => {
    render(<Report data={makeData()} />);
    // S001-RNA has no fastp / order_date / etc → many DASHes in its row.
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("taxon matrix renders one row per sample × one column per classifier with — for missing cells", () => {
    render(<Report data={makeData()} />);
    // HIV-1 has data only for S001-DNA; the S001-RNA row should show DASHes
    // for both classifier columns.
    const hivCard = screen.getByText("HIV-1").closest("li")!;
    const rows = within(hivCard).getAllByRole("row");
    // 1 header row + 2 sample rows
    expect(rows.length).toBe(3);
    // Find the RNA row by its sample_id label.
    const rnaRow = within(hivCard).getByText("S001-RNA").closest("tr")!;
    const rnaCells = within(rnaRow).getAllByText("—");
    // Two classifier columns × (reads + pct) = 4 DASHes
    expect(rnaCells.length).toBe(4);
  });
});
