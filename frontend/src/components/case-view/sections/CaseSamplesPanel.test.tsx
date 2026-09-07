import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import type { Sample, SampleReadDelta } from "../../../api/types";
import CaseSamplesPanel, { ntcCoverageWarning } from "./CaseSamplesPanel";

/**
 * The panel is what tells a clinician which samples were topped up on a
 * re-sequencing, and which were re-delivered with the same data they already
 * had — the latter meaning the sample is still short of the agreed depth.
 */

function sample(overrides: Partial<Sample> & { sample_id: string }): Sample {
  return {
    _id: `oid-${overrides.sample_id}`,
    sample_type: "sample",
    nucleic_acid: "DNA",
    total_reads: 1_000_000,
    ...overrides,
  } as Sample;
}

function delta(overrides: Partial<SampleReadDelta>): SampleReadDelta {
  return {
    status: "unchanged",
    current_reads: 1_000_000,
    previous_reads: 1_000_000,
    previous_version: 1,
    delta_reads: 0,
    pct_change: 0,
    ...overrides,
  };
}

function ntc(overrides: Partial<Sample> = {}): Sample {
  return sample({
    sample_id: "NTC-1",
    sample_type: "negative_ctrl",
    has_profile_data: true,
    ...overrides,
  });
}

function renderPanel(samples: Sample[]) {
  return render(<CaseSamplesPanel samples={samples} pathogenMap={{}} onSelectSample={() => {}} />);
}

function rowFor(sampleId: string) {
  return screen.getByText(sampleId).closest("tr") as HTMLElement;
}

describe("total reads", () => {
  it("renders the server-resolved count rather than picking a pipeline field", () => {
    // The count and the delta must describe the same number. Deriving it here
    // from taxprofiler/trana blocks let the two disagree on a document that
    // carried both.
    renderPanel([sample({ sample_id: "S1", total_reads: 2_345_678 })]);

    expect(within(rowFor("S1")).getByText("2,345,678")).toBeInTheDocument();
  });

  it("shows an em dash when the server could not resolve a count", () => {
    // sample_source is set so the only em dash in the row is the read count.
    renderPanel([sample({ sample_id: "S1", sample_source: "blood", total_reads: null })]);

    expect(within(rowFor("S1")).getByText("—")).toBeInTheDocument();
  });
});

describe("read-delta badges", () => {
  it("marks a topped-up sample with the size of the increase", () => {
    renderPanel([
      sample({
        sample_id: "S1",
        read_delta: delta({
          status: "increased",
          previous_reads: 1_000_000,
          current_reads: 2_500_000,
          delta_reads: 1_500_000,
          pct_change: 150,
        }),
      }),
    ]);

    const badge = within(rowFor("S1")).getByTitle(/v1:.*this run:.*\+150%/);
    expect(badge.textContent).toMatch(/▲/);
  });

  it("marks a sample that gained no data, rather than leaving the cell blank", () => {
    // The whole point of the feature: a blank cell would leave "still short of
    // depth" indistinguishable from "nothing to compare".
    renderPanel([sample({ sample_id: "S1", read_delta: delta({ status: "unchanged" }) })]);

    expect(within(rowFor("S1")).getByText("no top-up")).toBeInTheDocument();
  });

  it("marks a sample that lost reads", () => {
    renderPanel([
      sample({
        sample_id: "S1",
        read_delta: delta({
          status: "decreased",
          previous_reads: 1_200_000,
          current_reads: 1_000_000,
          delta_reads: -200_000,
          pct_change: -16.7,
        }),
      }),
    ]);

    expect(within(rowFor("S1")).getByTitle(/v1:/).textContent).toMatch(/▼/);
  });

  it("marks a sample absent from every earlier run as new", () => {
    renderPanel([
      sample({
        sample_id: "S1",
        read_delta: delta({
          status: "new",
          previous_reads: null,
          previous_version: null,
          delta_reads: null,
          pct_change: null,
        }),
      }),
    ]);

    const badge = within(rowFor("S1")).getByText("new");
    expect(badge).toHaveAttribute("title", expect.stringContaining("Not present"));
  });

  it("shows an uncomparable sample as unknown instead of unchanged", () => {
    renderPanel([
      sample({
        sample_id: "S1",
        read_delta: delta({
          status: "unknown",
          previous_reads: null,
          delta_reads: null,
          pct_change: null,
        }),
      }),
    ]);

    const row = rowFor("S1");
    expect(within(row).getByText("?")).toBeInTheDocument();
    expect(within(row).queryByText("no top-up")).not.toBeInTheDocument();
  });

  it("shows no badges on a case's first analysis", () => {
    // Nothing to compare against, so labelling rows would imply every sample
    // had failed to gain data.
    renderPanel([sample({ sample_id: "S1" }), sample({ sample_id: "S2" })]);

    expect(screen.queryByText("no top-up")).not.toBeInTheDocument();
    expect(screen.queryByText("new")).not.toBeInTheDocument();
  });
});

describe("negative-control coverage warning", () => {
  it("warns when the analysis has no negative control at all", () => {
    renderPanel([sample({ sample_id: "S1" })]);

    expect(screen.getByText(/No DNA negative control in this analysis/)).toBeInTheDocument();
  });

  it("stays quiet when every nucleic acid has a usable control", () => {
    renderPanel([sample({ sample_id: "S1" }), ntc()]);

    expect(screen.queryByText(/negative control/)).not.toBeInTheDocument();
  });

  it("names only the uncovered nucleic acid on a mixed-nucleic-acid case", () => {
    // Contaminant comparison is nucleic-acid-matched, so a DNA-only NTC leaves the
    // RNA samples uncontrolled — a warning ignoring nucleic acid would be wrong.
    const message = ntcCoverageWarning([
      sample({ sample_id: "S1", nucleic_acid: "DNA" }),
      sample({ sample_id: "S2", nucleic_acid: "RNA" }),
      ntc({ nucleic_acid: "DNA" }),
    ]);

    expect(message).toMatch(/No RNA negative control/);
    expect(message).not.toMatch(/DNA negative control/);
  });

  it("distinguishes a control that produced no classifier data from an absent one", () => {
    const message = ntcCoverageWarning([
      sample({ sample_id: "S1" }),
      ntc({ has_profile_data: false }),
    ]);

    expect(message).toMatch(/produced no classifier data/);
  });

  it("does not claim an empty control when the server did not say so", () => {
    // An older response without has_profile_data must not be reported as a
    // failed control.
    const message = ntcCoverageWarning([
      sample({ sample_id: "S1" }),
      sample({ sample_id: "NTC-1", sample_type: "negative_ctrl" }),
    ]);

    expect(message).toBeNull();
  });

  it("stays quiet on a controls-only analysis", () => {
    expect(ntcCoverageWarning([ntc()])).toBeNull();
  });
});
