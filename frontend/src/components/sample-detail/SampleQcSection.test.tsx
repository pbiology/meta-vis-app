import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SampleQcSection from "./SampleQcSection";
import type { SampleQcSummary } from "../../utils/sampleQc";

const taxprofiler: SampleQcSummary = {
  pipeline: "taxprofiler",
  rawReads: 1_000_000,
  passedReads: 812_000,
  passedPct: 81.2,
  hostPct: 38,
  nonHostReads: 503_440,
  q20Pct: 97.5,
  q30Pct: 92.1,
};

describe("SampleQcSection", () => {
  it("shows a one-line summary and hides the details by default", () => {
    render(<SampleQcSection qc={taxprofiler} />);

    expect(
      screen.getByText("81.2% passed · 38.0% host · 503,440 non-host · Q30 92.1%")
    ).toBeInTheDocument();
    expect(screen.queryByText("Q20 rate")).not.toBeInTheDocument();
  });

  it("opens the full metrics, including Q20 and raw reads, on request", async () => {
    render(<SampleQcSection qc={taxprofiler} />);

    await userEvent.click(screen.getByRole("button", { name: "Details" }));

    expect(screen.getByText("Q20 rate")).toBeInTheDocument();
    expect(screen.getByText("97.5%")).toBeInTheDocument();
    expect(screen.getByText("1,000,000")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hide details" })).toHaveAttribute(
      "aria-expanded",
      "true"
    );
  });

  it("summarises a TRANA sample with its own metrics", () => {
    render(
      <SampleQcSection
        qc={{
          pipeline: "trana",
          rawReads: 5_000,
          passedReads: 4_000,
          meanLength: 1_450,
          meanQuality: 14.2,
          n50: 1_500,
        }}
      />
    );

    expect(screen.getByText("4,000 passed · mean Q 14.2 · N50 1,500 bp")).toBeInTheDocument();
  });

  it("says so when the sample has no QC block", () => {
    render(<SampleQcSection qc={null} />);

    expect(screen.getByText("No QC data for this sample.")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
