import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import Report from "./Report";
import type { ReportData } from "./useReportData";

function makeData(overrides: Partial<ReportData> = {}): ReportData {
  return {
    generatedAt: "2026-04-29T10:00:00Z",
    sample: {
      sample_id: "S001",
      case_id: "C001",
      sample_type: "sample",
      material: "DNA",
      taxprofiler: {
        fastp: {
          total_reads_before_filtering: 1000000,
          passed_filter_reads: 950000,
          q20_rate: 0.97,
          q30_rate: 0.93,
        },
      },
    },
    subject: { subject_id: "SUB-1", sex: "F" },
    taxa: [
      {
        taxon_id: 11676,
        name: "HIV-1",
        rank: "species",
        superkingdom: "Viruses",
        pathogen: true,
        abundance: { kraken2: 1234 },
        pct: { kraken2: 0.123 },
      },
      {
        taxon_id: 562,
        name: "Escherichia coli",
        rank: "species",
        superkingdom: "Bacteria",
        pathogen: false,
        abundance: { kraken2: 50 },
        pct: { kraken2: 0.005 },
      },
    ],
    notes: [{ id: "n1", author: "alice", created_at: "2026-04-28", text: "Looks suspicious" }],
    sampleNote: "Followup ordered",
    pipelineInfo: {
      pipeline_name: "taxprofiler",
      pipeline_version: "1.2.3",
      nextflow_version: "23.10.0",
      tools: { kraken2: "2.1.3", fastp: "0.23.4" },
    },
    ...overrides,
  };
}

describe("Report", () => {
  it("renders all five sections from a populated fixture", () => {
    render(<Report data={makeData()} />);
    expect(screen.getByText("Sample information")).toBeInTheDocument();
    expect(screen.getByText("Subject")).toBeInTheDocument();
    expect(screen.getByText("Taxa of interest")).toBeInTheDocument();
    expect(screen.getByText("Comments")).toBeInTheDocument();
    expect(screen.getByText("Provenance")).toBeInTheDocument();
  });

  it("flags pathogen taxa with the pathogen modifier class", () => {
    render(<Report data={makeData()} />);
    const hivItem = screen.getByText("HIV-1").closest("li")!;
    const ecoliItem = screen.getByText("Escherichia coli").closest("li")!;
    expect(hivItem.className).toContain("report-taxon-pathogen");
    expect(ecoliItem.className).not.toContain("report-taxon-pathogen");
  });

  it("renders 'Not linked' when subject is null", () => {
    render(<Report data={makeData({ subject: null })} />);
    expect(screen.getByText("Not linked")).toBeInTheDocument();
  });

  it("wraps the provenance section in .report-page-break", () => {
    const { container } = render(<Report data={makeData()} />);
    const wrapper = container.querySelector(".report-page-break");
    expect(wrapper).not.toBeNull();
    // Provenance heading is inside the wrapper, not the body page.
    expect(within(wrapper as HTMLElement).getByText("Provenance")).toBeInTheDocument();
  });

  it("renders em-dash for missing sample fields", () => {
    const data = makeData({
      sample: { sample_id: "S001", case_id: "C001", sample_type: "sample", material: "DNA" },
    });
    render(<Report data={data} />);
    // At least one em-dash should appear because order_date / received_at etc. are absent.
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});
